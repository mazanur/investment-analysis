"""
Tests for SmartLab financial data fetching job.

Uses mocked HTTP responses to test CSV parsing and DB writing logic.

Author: AlmazNurmukhametov
"""

from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import select

from app.jobs.fetch_smartlab import (
    _parse_value,
    _detect_period_type,
    parse_smartlab_csv,
    run_fetch_smartlab,
)
from app.models import Company
from app.models.enums import PeriodTypeEnum
from app.models.financial_report import FinancialReport

API_KEY = "dev-api-key"
HEADERS = {"X-API-Key": API_KEY}


# ============================================================
# Sample SmartLab CSV data (semicolon-separated, metrics as rows)
# ============================================================

SAMPLE_YEARLY_CSV = (
    b';2022;2023;2024;LTM\n'
    b'"\\xd0\\x94\\xd0\\xb0\\xd1\\x82\\xd0\\xb0 \\xd0\\xbe\\xd1\\x82\\xd1\\x87\\xd0\\xb5\\xd1\\x82\\xd0\\xb0";;;27.02.2025;26.02.2026\n'
    b'"\\xd0\\x92\\xd0\\xb0\\xd0\\xbb\\xd1\\x8e\\xd1\\x82\\xd0\\xb0 \\xd0\\xbe\\xd1\\x82\\xd1\\x87\\xd0\\xb5\\xd1\\x82\\xd0\\xb0";RUB;RUB;RUB;RUB\n'
)

# Use properly encoded UTF-8 for the sample CSV
SAMPLE_YEARLY_CSV_UTF8 = (
    ';2022;2023;2024;LTM\n'
    '"Дата отчета";;;27.02.2025;26.02.2026\n'
    '"Валюта отчета";RUB;RUB;RUB;RUB\n'
    '"Выручка, млрд руб";"7 928";"8 622";"7 890";"7 890"\n'
    '"Чистая прибыль, млрд руб";790.0;"1 155";848.5;545.3\n'
    '"Чистые активы, млрд руб";;"6 384";"6 826";"5 380"\n'
    '"Долг, млрд руб";;396.0;380.0;344.6\n'
    '"Чистый долг, млрд руб";0.00;-784.0;"-1 146";-231.5\n'
    '"EBITDA, млрд руб";;"2 005";"1 785";"1 406"\n'
    '"CAPEX, млрд руб";;720.0;780.0;839.8\n'
    '"FCF, млрд руб";;964.0;979.0;846.5\n'
    '"Дивиденд, руб/акцию";694;945;1055;938\n'
    '"Див доход, ао, %";17.0%;14.0%;14.6%;18.3%\n'
).encode('utf-8')

SAMPLE_QUARTERLY_CSV_UTF8 = (
    ';2024Q1;2024Q2;2024Q3;2024Q4;LTM\n'
    '"Дата отчета";26.04.2024;08.08.2024;31.10.2024;27.02.2025;29.08.2025\n'
    '"Валюта отчета";RUB;RUB;RUB;RUB;RUB\n'
    '"Чистая прибыль, млрд руб";397.6;418.7;411.1;352.9;436.0\n'
    '"Чистый операц доход, млрд руб";801.9;855.7;965.1;"1 196";"1 068"\n'
    '"Капитал, млрд руб";"6 904";"6 417";"6 700";"7 176";"7 629"\n'
    '"Просроченные кредиты, NPL, %";3.50%;3.50%;3.70%;4.10%;4.50%\n'
    '"Стоимость риска (CoR), %";0.500%;1.000%;1.20%;1.19%;1.24%\n'
).encode('utf-8')

SAMPLE_BANK_YEARLY_CSV_UTF8 = (
    ';2023;2024;2025;LTM\n'
    '"Дата отчета";28.02.2024;27.02.2025;26.02.2026;26.02.2026\n'
    '"Валюта отчета";RUB;RUB;RUB;RUB\n'
    '"Чистый операц доход, млрд руб";"3 428";"3 819";"4 240";"4 240"\n'
    '"Чистая прибыль, млрд руб";"1 509";"1 582";"1 707";"1 707"\n'
    '"Капитал, млрд руб";"6 584";"7 176";"8 352";"8 352"\n'
    '"Чистый долг, млрд руб";"-2 387";"-2 252";"-3 938";"-3 938"\n'
    '"Чист. проц. доходы, млрд руб";"2 565";"3 000";"3 556";"3 556"\n'
    '"Депозиты, млрд руб";"36 693";"44 627";"49 374";"49 374"\n'
    '"Кредитный портфель, млрд руб";"37 558";"40 921";"44 312";"44 312"\n'
    '"Просроченные кредиты, NPL, %";3.40%;3.70%;;\n'
).encode('utf-8')

EMPTY_CSV = ';2024\n"Дата отчета";\n"Валюта отчета";RUB\n'.encode('utf-8')

HTML_ERROR_PAGE = b'<html><body>Error 404</body></html>'


# ============================================================
# Unit tests: value parsing
# ============================================================


def test_parse_value_number():
    assert _parse_value("280.50") == 280.50


def test_parse_value_with_spaces():
    assert _parse_value("1 301") == 1301.0


def test_parse_value_negative_with_spaces():
    assert _parse_value("-1 291") == -1291.0


def test_parse_value_quoted_negative():
    assert _parse_value('"-1 291"') == -1291.0


def test_parse_value_comma_decimal():
    assert _parse_value("2,08") == 2.08


def test_parse_value_percentage():
    assert _parse_value("3.5%") == 3.5


def test_parse_value_zero_pct():
    assert _parse_value("0.0%") == 0.0


def test_parse_value_empty():
    assert _parse_value("") is None
    assert _parse_value("  ") is None
    assert _parse_value(None) is None


def test_parse_value_plain_int():
    assert _parse_value("694") == 694.0


# ============================================================
# Unit tests: period type detection
# ============================================================


def test_detect_period_type_yearly():
    assert _detect_period_type("2024") == PeriodTypeEnum.yearly


def test_detect_period_type_quarterly():
    assert _detect_period_type("2024Q1") == PeriodTypeEnum.quarterly
    assert _detect_period_type("2023Q4") == PeriodTypeEnum.quarterly


def test_detect_period_type_ltm():
    assert _detect_period_type("LTM") == PeriodTypeEnum.ltm


# ============================================================
# Unit tests: CSV parsing
# ============================================================


def test_parse_yearly_csv():
    result = parse_smartlab_csv(SAMPLE_YEARLY_CSV_UTF8, "yearly")
    assert len(result) == 4  # 2022, 2023, 2024, LTM

    # Check 2024
    y2024 = next(r for r in result if r["period"] == "2024")
    assert y2024["period_type"] == PeriodTypeEnum.yearly
    assert y2024["revenue"] == 7890.0
    assert y2024["net_income"] == 848.5
    assert y2024["equity"] == 6826.0
    assert y2024["total_debt"] == 380.0
    assert y2024["net_debt"] == -1146.0
    assert y2024["extra_metrics"]["ebitda"] == 1785.0
    assert y2024["extra_metrics"]["capex"] == 780.0
    assert y2024["extra_metrics"]["fcf"] == 979.0
    assert y2024["extra_metrics"]["dividend_per_share"] == 1055.0
    assert y2024["dividend_yield"] == 14.6


def test_parse_quarterly_csv():
    result = parse_smartlab_csv(SAMPLE_QUARTERLY_CSV_UTF8, "quarterly")
    assert len(result) == 5  # 2024Q1-Q4 + LTM

    q1 = next(r for r in result if r["period"] == "2024Q1")
    assert q1["period_type"] == PeriodTypeEnum.quarterly
    assert q1["net_income"] == 397.6
    assert q1["revenue"] == 801.9  # From "Чистый операц доход" (bank)
    assert q1["equity"] == 6904.0
    assert q1["extra_metrics"]["npl_ratio"] == 3.5
    assert q1["extra_metrics"]["cost_of_risk"] == 0.5


def test_parse_bank_yearly_csv():
    result = parse_smartlab_csv(SAMPLE_BANK_YEARLY_CSV_UTF8, "yearly")
    assert len(result) == 4

    y2024 = next(r for r in result if r["period"] == "2024")
    assert y2024["revenue"] == 3819.0  # From "Чистый операц доход"
    assert y2024["net_income"] == 1582.0
    assert y2024["equity"] == 7176.0
    assert y2024["net_debt"] == -2252.0
    assert y2024["extra_metrics"]["net_interest_income"] == 3000.0
    assert y2024["extra_metrics"]["deposits"] == 44627.0
    assert y2024["extra_metrics"]["loan_portfolio"] == 40921.0


def test_parse_ltm_period():
    result = parse_smartlab_csv(SAMPLE_YEARLY_CSV_UTF8, "yearly")
    ltm = next(r for r in result if r["period"] == "LTM")
    assert ltm["period_type"] == PeriodTypeEnum.ltm


def test_parse_report_dates():
    result = parse_smartlab_csv(SAMPLE_YEARLY_CSV_UTF8, "yearly")
    y2024 = next(r for r in result if r["period"] == "2024")
    assert y2024["report_date"] == "27.02.2025"


def test_parse_empty_csv():
    result = parse_smartlab_csv(EMPTY_CSV)
    assert result == []


def test_parse_too_short_csv():
    result = parse_smartlab_csv(b"short")
    assert result == []


# ============================================================
# Integration tests: run_fetch_smartlab
# ============================================================


def _mock_response(content: bytes, status_code: int = 200):
    """Create a mock httpx.Response."""
    request = httpx.Request("GET", "http://mock")
    return httpx.Response(status_code, content=content, request=request)


@pytest.mark.asyncio
async def test_run_fetch_smartlab(db_session):
    company = Company(ticker="LKOH", name="ЛУКОЙЛ")
    db_session.add(company)
    await db_session.commit()

    async def mock_get(self, url, **kwargs):
        if "/f/y/" in url:
            return _mock_response(SAMPLE_YEARLY_CSV_UTF8)
        return _mock_response(SAMPLE_QUARTERLY_CSV_UTF8)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_smartlab(db_session, "LKOH")

    assert result["ticker"] == "LKOH"
    assert result["yearly"] > 0
    assert result["quarterly"] > 0
    assert result["errors"] == []

    # Verify data in DB
    stmt = select(FinancialReport).where(FinancialReport.company_id == company.id)
    reports = (await db_session.execute(stmt)).scalars().all()
    assert len(reports) > 0

    yearly_2024 = next((r for r in reports if r.period == "2024"), None)
    assert yearly_2024 is not None
    assert yearly_2024.period_type == PeriodTypeEnum.yearly
    assert yearly_2024.net_income == Decimal("848.5")
    assert yearly_2024.revenue == Decimal("7890")


@pytest.mark.asyncio
async def test_run_fetch_smartlab_yearly_only(db_session):
    company = Company(ticker="SBER", name="Sberbank")
    db_session.add(company)
    await db_session.commit()

    async def mock_get(self, url, **kwargs):
        return _mock_response(SAMPLE_BANK_YEARLY_CSV_UTF8)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_smartlab(db_session, "SBER", period_types=["yearly"])

    assert result["yearly"] > 0
    assert result["quarterly"] == 0


@pytest.mark.asyncio
async def test_run_fetch_smartlab_upsert(db_session):
    """Running twice should upsert, not duplicate."""
    company = Company(ticker="LKOH", name="ЛУКОЙЛ")
    db_session.add(company)
    await db_session.commit()

    async def mock_get(self, url, **kwargs):
        if "/f/y/" in url:
            return _mock_response(SAMPLE_YEARLY_CSV_UTF8)
        return _mock_response(SAMPLE_QUARTERLY_CSV_UTF8)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        await run_fetch_smartlab(db_session, "LKOH")
        result = await run_fetch_smartlab(db_session, "LKOH")

    assert result["errors"] == []

    stmt = select(FinancialReport).where(FinancialReport.company_id == company.id)
    reports = (await db_session.execute(stmt)).scalars().all()
    periods = [r.period for r in reports]
    # No duplicates
    assert len(periods) == len(set(periods))


@pytest.mark.asyncio
async def test_run_fetch_smartlab_company_not_found(db_session):
    async def mock_get(self, url, **kwargs):
        return _mock_response(SAMPLE_YEARLY_CSV_UTF8)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_smartlab(db_session, "NONEXIST")

    assert "not found" in result["errors"][0]


@pytest.mark.asyncio
async def test_run_fetch_smartlab_html_error(db_session):
    company = Company(ticker="LKOH", name="ЛУКОЙЛ")
    db_session.add(company)
    await db_session.commit()

    async def mock_get(self, url, **kwargs):
        return _mock_response(HTML_ERROR_PAGE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_smartlab(db_session, "LKOH")

    assert result["yearly"] == 0
    assert result["quarterly"] == 0
    assert len(result["errors"]) > 0


@pytest.mark.asyncio
async def test_run_fetch_smartlab_api_failure(db_session):
    company = Company(ticker="LKOH", name="ЛУКОЙЛ")
    db_session.add(company)
    await db_session.commit()

    async def mock_get(self, url, **kwargs):
        raise httpx.ConnectError("Connection refused")

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_smartlab(db_session, "LKOH")

    assert result["yearly"] == 0
    assert len(result["errors"]) > 0


# ============================================================
# API endpoint tests
# ============================================================


@pytest.mark.asyncio
async def test_trigger_fetch_smartlab_endpoint(client):
    await client.post(
        "/companies/LKOH",
        json={"ticker": "LKOH", "name": "ЛУКОЙЛ"},
        headers=HEADERS,
    )

    async def mock_get(self, url, **kwargs):
        if "/f/y/" in url:
            return _mock_response(SAMPLE_YEARLY_CSV_UTF8)
        return _mock_response(SAMPLE_QUARTERLY_CSV_UTF8)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        resp = await client.post("/jobs/fetch-smartlab/LKOH", headers=HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "LKOH"
    assert data["yearly"] > 0


@pytest.mark.asyncio
async def test_trigger_fetch_smartlab_requires_api_key(client):
    resp = await client.post("/jobs/fetch-smartlab/LKOH")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_trigger_fetch_smartlab_with_period_types(client):
    await client.post(
        "/companies/SBER",
        json={"ticker": "SBER", "name": "Sberbank"},
        headers=HEADERS,
    )

    async def mock_get(self, url, **kwargs):
        return _mock_response(SAMPLE_BANK_YEARLY_CSV_UTF8)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        resp = await client.post(
            "/jobs/fetch-smartlab/SBER?period_types=yearly",
            headers=HEADERS,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["yearly"] > 0
    assert data["quarterly"] == 0
