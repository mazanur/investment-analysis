"""
Fetch financial reports from smart-lab.ru.

Ports logic from scripts/download_smartlab.py:
- Downloads yearly/quarterly MSFO CSV for a ticker
- Parses transposed CSV (metrics as rows, periods as columns)
- Upserts into financial_reports table with extra_metrics JSONB

smart-lab.ru is a public financial data site, no auth required.

Author: AlmazNurmukhametov
"""

import asyncio
import csv
import io
import logging
import re
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company
from app.models.financial_report import FinancialReport
from app.models.enums import PeriodTypeEnum

logger = logging.getLogger(__name__)

SMARTLAB_TIMEOUT = 30.0
YEARLY_URL = "https://smart-lab.ru/q/{ticker}/f/y/MSFO/download/"
QUARTERLY_URL = "https://smart-lab.ru/q/{ticker}/f/q/MSFO/download/"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Mapping: CSV metric name prefix → DB field name
# Values in CSV are in billions (млрд руб), stored as-is
METRIC_TO_FIELD = {
    "Чистая прибыль, млрд руб": "net_income",
    "Выручка, млрд руб": "revenue",
    "Чистый операц доход, млрд руб": "revenue",  # banks use this instead of revenue
    "Капитал, млрд руб": "equity",
    "Чистые активы, млрд руб": "equity",  # non-banks use this
    "Долг, млрд руб": "total_debt",
    "Чистый долг, млрд руб": "net_debt",
}

# Percentage metrics that go into extra_metrics (strip % sign)
PCT_METRICS = {
    "Див доход, ао, %",
    "Див доход, ап, %",
    "Дивиденды/прибыль, %",
    "Дост.осн капитала, %",
    "Дост. общ капитала, %",
    "Стоимость риска (CoR), %",
    "Расходы/Доходы (CIR), %",
    "Loan-to-deposit ratio, %",
    "Просроченные кредиты, NPL, %",
}

# Metrics to skip entirely (not useful for DB)
SKIP_METRICS = {
    "Дата отчета",
    "Валюта отчета",
}

# Extra metrics: metric name → key name in extra_metrics JSONB
EXTRA_METRIC_KEYS = {
    "EBITDA, млрд руб": "ebitda",
    "CAPEX, млрд руб": "capex",
    "FCF, млрд руб": "fcf",
    "Операционная прибыль, млрд руб": "operating_profit",
    "Операционный денежный поток, млрд руб": "operating_cashflow",
    "Див.выплата, млрд руб": "dividend_payout",
    "Дивиденд, руб/акцию": "dividend_per_share",
    "Опер. расходы, млрд руб": "operating_expenses",
    "Себестоимость, млрд руб": "cost_of_goods",
    "Процентные расходы, млрд руб": "interest_expenses",
    "Создание резервов, млрд руб": "provisions",
    "Активы, млрд руб": "total_assets",
    "Активы банка, млрд руб": "total_assets",
    "Наличность, млрд руб": "cash",
    "Кредитный портфель, млрд руб": "loan_portfolio",
    "Депозиты, млрд руб": "deposits",
    "Чист. проц. доходы, млрд руб": "net_interest_income",
    "Чист. комисс. доход, млрд руб": "net_commission_income",
    "Добыча нефти, млн т": "oil_production_mt",
    "Переработка нефти, млн т": "oil_refining_mt",
    "Добыча газа, млрд м3": "gas_production_bcm",
    "Амортизация, млрд руб": "depreciation",
    "Число клиентов, млн": "clients_mln",
    "Число акций ао, млн": "shares_mln",
    "Цена акции ао, руб": "share_price",
    "Расх на персонал, млрд руб": "staff_expenses",
    "Кредиты юрлицам, млрд руб": "corporate_loans",
    "Кредиты физлицам, млрд руб": "retail_loans",
    "Депозиты юрлиц, млрд руб": "corporate_deposits",
    "Депозиты физлиц, млрд руб": "retail_deposits",
}

# PCT_METRICS → extra_metrics key mapping
PCT_METRIC_KEYS = {
    "Див доход, ао, %": "dividend_yield_common",
    "Див доход, ап, %": "dividend_yield_preferred",
    "Дивиденды/прибыль, %": "payout_ratio",
    "Дост.осн капитала, %": "tier1_ratio",
    "Дост. общ капитала, %": "total_capital_ratio",
    "Стоимость риска (CoR), %": "cost_of_risk",
    "Расходы/Доходы (CIR), %": "cost_income_ratio",
    "Loan-to-deposit ratio, %": "loan_deposit_ratio",
    "Просроченные кредиты, NPL, %": "npl_ratio",
}


def _parse_value(raw: str) -> float | None:
    """Parse a SmartLab CSV value to float.

    Handles: empty, spaces as thousands sep, comma as decimal, percentages,
    quoted negative numbers like "-1 291".
    """
    if not raw or not raw.strip():
        return None

    s = raw.strip().strip('"')
    if not s:
        return None

    # Percentage: "3.5%" or "0.0%"
    is_pct = s.endswith("%")
    if is_pct:
        s = s[:-1]

    # Replace comma with dot (decimal separator)
    s = s.replace(",", ".")

    # Remove space thousands separator: "1 301" → "1301"
    # But preserve negative sign: "-1 291" → "-1291"
    s = re.sub(r"(?<=\d)\s+(?=\d)", "", s)

    try:
        return float(s)
    except ValueError:
        return None


def _detect_period_type(label: str) -> PeriodTypeEnum:
    """Detect period type from column header label."""
    if label.upper() == "LTM":
        return PeriodTypeEnum.ltm
    if "Q" in label.upper():
        return PeriodTypeEnum.quarterly
    return PeriodTypeEnum.yearly


def parse_smartlab_csv(csv_bytes: bytes, period_type_hint: str = "yearly") -> list[dict]:
    """Parse SmartLab CSV into list of period dicts.

    Args:
        csv_bytes: Raw CSV content from smart-lab.ru
        period_type_hint: "yearly" or "quarterly" — used as fallback

    Returns:
        List of dicts, one per period:
        {
            "period": "2024",
            "period_type": PeriodTypeEnum.yearly,
            "report_date": "27.02.2025" or None,
            "net_income": 1582.0,
            "revenue": 3819.0,
            ...
            "extra_metrics": {"ebitda": 1200.0, "npl_ratio": 3.7, ...}
        }
    """
    text = csv_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)

    if len(rows) < 4:
        return []

    # Row 0: header — period labels
    header = rows[0]
    periods = header[1:]  # skip first empty column

    # Row 1: report dates
    report_dates_row = rows[1] if len(rows) > 1 else []
    report_dates = report_dates_row[1:] if len(report_dates_row) > 1 else []

    # Initialize result: one dict per period
    results: dict[int, dict] = {}
    for i, period_label in enumerate(periods):
        label = period_label.strip().strip('"')
        if not label:
            continue
        pt = _detect_period_type(label)
        report_date = report_dates[i].strip().strip('"') if i < len(report_dates) else ""

        results[i] = {
            "period": label,
            "period_type": pt,
            "report_date": report_date if report_date else None,
            "net_income": None,
            "revenue": None,
            "equity": None,
            "total_debt": None,
            "net_debt": None,
            "extra_metrics": {},
        }

    # Parse data rows (skip header, report date, currency rows)
    for row in rows[1:]:
        if not row:
            continue
        metric_name = row[0].strip().strip('"')

        if not metric_name or metric_name in SKIP_METRICS:
            continue

        values = row[1:]

        for i, raw_val in enumerate(values):
            if i not in results:
                continue

            val = _parse_value(raw_val)
            if val is None:
                continue

            # Check if it maps to a direct DB field
            field_name = METRIC_TO_FIELD.get(metric_name)
            if field_name:
                # Don't overwrite if already set (e.g., "revenue" from bank metric)
                if results[i][field_name] is None:
                    results[i][field_name] = val
                continue

            # Check if it's a percentage metric
            if metric_name in PCT_METRICS:
                key = PCT_METRIC_KEYS.get(metric_name)
                if key:
                    results[i]["extra_metrics"][key] = val
                continue

            # Check if it's a known extra metric
            key = EXTRA_METRIC_KEYS.get(metric_name)
            if key:
                results[i]["extra_metrics"][key] = val
                continue

            # Unknown metric — skip (don't bloat extra_metrics with everything)

    # Filter out periods with no data at all
    return [
        r for r in results.values()
        if any(r[f] is not None for f in ("net_income", "revenue", "equity", "total_debt", "net_debt"))
        or r["extra_metrics"]
    ]


async def _fetch_csv(client: httpx.AsyncClient, url: str) -> bytes | None:
    """Download CSV from smart-lab.ru with retry."""
    for attempt in range(3):
        try:
            resp = await client.get(
                url,
                timeout=SMARTLAB_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            )
            resp.raise_for_status()
            data = resp.content

            # Validate: not an HTML error page, and has content
            if data[:5] in (b"<html", b"<!DOC"):
                logger.warning("SmartLab returned HTML instead of CSV for %s", url)
                return None
            if len(data) < 50:
                logger.warning("SmartLab response too small (%d bytes) for %s", len(data), url)
                return None

            return data
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("SmartLab fetch attempt %d failed: %s", attempt + 1, e)
            if attempt == 2:
                return None
            await asyncio.sleep(2**attempt)


async def _upsert_reports(
    db: AsyncSession,
    company_id: int,
    parsed: list[dict],
) -> int:
    """Upsert parsed SmartLab data into financial_reports. Returns count."""
    if not parsed:
        return 0

    periods = [p["period"] for p in parsed]
    stmt = select(FinancialReport).where(
        FinancialReport.company_id == company_id,
        FinancialReport.period.in_(periods),
    )
    result = await db.execute(stmt)
    existing = {r.period: r for r in result.scalars().all()}

    count = 0
    for data in parsed:
        period = data["period"]

        # Convert report_date from DD.MM.YYYY to date
        report_date = None
        if data.get("report_date"):
            try:
                parts = data["report_date"].split(".")
                if len(parts) == 3:
                    from datetime import date
                    report_date = date(int(parts[2]), int(parts[1]), int(parts[0]))
            except (ValueError, IndexError):
                pass

        def to_decimal(val):
            if val is None:
                return None
            try:
                return Decimal(str(val))
            except (InvalidOperation, ValueError):
                return None

        fields = {
            "period_type": data["period_type"],
            "report_date": report_date,
            "net_income": to_decimal(data["net_income"]),
            "revenue": to_decimal(data["revenue"]),
            "equity": to_decimal(data["equity"]),
            "total_debt": to_decimal(data["total_debt"]),
            "net_debt": to_decimal(data["net_debt"]),
            "extra_metrics": data["extra_metrics"] if data["extra_metrics"] else None,
        }

        if period in existing:
            report = existing[period]
            for k, v in fields.items():
                setattr(report, k, v)
        else:
            report = FinancialReport(
                company_id=company_id,
                period=period,
                **fields,
            )
            db.add(report)
        count += 1

    return count


async def run_fetch_smartlab(
    db: AsyncSession,
    ticker: str,
    period_types: list[str] | None = None,
) -> dict:
    """
    Main job: fetch SmartLab financial data for a ticker and upsert into DB.

    Args:
        db: Database session
        ticker: Company ticker (e.g., "SBER")
        period_types: List of period types to fetch: ["yearly", "quarterly"].
                      If None, fetches both.

    Returns:
        dict with results: {"ticker": str, "yearly": int, "quarterly": int, "errors": list[str]}
    """
    result = {"ticker": ticker, "yearly": 0, "quarterly": 0, "errors": []}

    if period_types is None:
        period_types = ["yearly", "quarterly"]

    # Find company in DB
    stmt = select(Company).where(Company.ticker == ticker)
    company_result = await db.execute(stmt)
    company = company_result.scalar_one_or_none()

    if not company:
        result["errors"].append(f"Company {ticker} not found in database")
        return result

    async with httpx.AsyncClient() as client:
        for pt in period_types:
            url = YEARLY_URL.format(ticker=ticker) if pt == "yearly" else QUARTERLY_URL.format(ticker=ticker)
            csv_bytes = await _fetch_csv(client, url)

            if not csv_bytes:
                result["errors"].append(f"Failed to fetch {pt} CSV for {ticker}")
                continue

            parsed = parse_smartlab_csv(csv_bytes, period_type_hint=pt)
            if not parsed:
                result["errors"].append(f"No data parsed from {pt} CSV for {ticker}")
                continue

            count = await _upsert_reports(db, company.id, parsed)
            result[pt] = count

    await db.commit()
    return result
