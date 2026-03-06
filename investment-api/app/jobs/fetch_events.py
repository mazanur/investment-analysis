"""
Fetch dividends and corporate events from MOEX ISS API.

Ports logic from scripts/download_moex_events.py:
- Fetches dividend data per ticker from MOEX ISS
- Upserts into dividends table

MOEX ISS API is public, no auth required.

Author: AlmazNurmukhametov
"""

import asyncio
import logging
from datetime import date
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company
from app.models.dividend import Dividend
from app.models.enums import DividendStatusEnum

logger = logging.getLogger(__name__)

MOEX_TIMEOUT = 30.0
MOEX_BASE = "https://iss.moex.com/iss"

DIVIDENDS_URL = (
    MOEX_BASE + "/securities/{ticker}/dividends.json"
    "?iss.meta=off&iss.json=extended"
)


async def _fetch_json(client: httpx.AsyncClient, url: str) -> list | dict | None:
    """Fetch JSON from MOEX ISS API with retries and backoff."""
    for attempt in range(3):
        try:
            resp = await client.get(url, timeout=MOEX_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("MOEX fetch attempt %d failed: %s", attempt + 1, e)
            if attempt == 2:
                return None
            await asyncio.sleep(2**attempt)


def parse_dividends(data: list) -> list[dict]:
    """Parse MOEX ISS dividends response.

    MOEX returns iss.json=extended format:
    [{"dividends": [{"registryclosedate": "2025-07-18", "value": 34.84, "currencyid": "SUR"}, ...]}]

    Returns list of dicts with parsed dividend info.
    """
    dividends = []
    if not data or not isinstance(data, list):
        return dividends

    for block in data:
        if not isinstance(block, dict):
            continue
        divs = block.get("dividends")
        if not divs or not isinstance(divs, list):
            continue
        for d in divs:
            if not isinstance(d, dict):
                continue

            record_date_str = d.get("registryclosedate", "")
            value = d.get("value", 0)
            currency = d.get("currencyid", "")

            if not record_date_str or not value:
                continue

            # Parse date
            try:
                record_date = date.fromisoformat(record_date_str[:10])
            except (ValueError, TypeError):
                continue

            # Map MOEX currency codes
            if currency in ("SUR", "RUB", ""):
                currency = "RUB"
            elif currency == "USD":
                currency = "USD"

            dividends.append({
                "record_date": record_date,
                "amount": value,
                "currency": currency,
            })

    return dividends


def _determine_status(record_date: date) -> DividendStatusEnum:
    """Determine dividend status based on record date vs today."""
    today = date.today()
    if record_date < today:
        return DividendStatusEnum.paid
    return DividendStatusEnum.announced


async def _upsert_dividends(
    db: AsyncSession,
    company_id: int,
    parsed: list[dict],
) -> int:
    """Upsert parsed dividends into DB. Returns count of upserted rows."""
    if not parsed:
        return 0

    dates = [d["record_date"] for d in parsed]
    stmt = select(Dividend).where(
        Dividend.company_id == company_id,
        Dividend.record_date.in_(dates),
    )
    result = await db.execute(stmt)
    existing = {d.record_date: d for d in result.scalars().all()}

    count = 0
    for data in parsed:
        rd = data["record_date"]

        try:
            amount = Decimal(str(data["amount"]))
        except (InvalidOperation, ValueError):
            continue

        status = _determine_status(rd)

        if rd in existing:
            div = existing[rd]
            div.amount = amount
            div.currency = data["currency"]
            div.status = status
        else:
            div = Dividend(
                company_id=company_id,
                record_date=rd,
                amount=amount,
                currency=data["currency"],
                status=status,
            )
            db.add(div)
        count += 1

    return count


async def run_fetch_events(
    db: AsyncSession,
    ticker: str,
) -> dict:
    """
    Main job: fetch dividends from MOEX ISS for a ticker and upsert into DB.

    Args:
        db: Database session
        ticker: Company ticker (e.g., "SBER")

    Returns:
        dict with results: {"ticker": str, "dividends": int, "errors": list[str]}
    """
    result = {"ticker": ticker, "dividends": 0, "errors": []}

    # Find company in DB
    stmt = select(Company).where(Company.ticker == ticker)
    company_result = await db.execute(stmt)
    company = company_result.scalar_one_or_none()

    if not company:
        result["errors"].append(f"Company {ticker} not found in database")
        return result

    async with httpx.AsyncClient() as client:
        url = DIVIDENDS_URL.format(ticker=ticker)
        data = await _fetch_json(client, url)

        if data is None:
            result["errors"].append(f"Failed to fetch dividends from MOEX for {ticker}")
            return result

        parsed = parse_dividends(data)
        if not parsed:
            # Not an error — some companies have no dividends
            return result

        count = await _upsert_dividends(db, company.id, parsed)
        result["dividends"] = count

    await db.commit()
    return result
