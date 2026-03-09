"""
Tests for MOEX events (dividends) fetching job.

Uses mocked MOEX API responses to test parsing and DB writing logic.

Author: AlmazNurmukhametov
"""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import select

from app.jobs.fetch_events import (
    parse_dividends,
    run_fetch_events,
)
from app.models import Company
from app.models.dividend import Dividend
from app.models.enums import DividendStatusEnum

API_KEY = "dev-api-key"
HEADERS = {"X-API-Key": API_KEY}


# ============================================================
# Sample MOEX ISS API responses (iss.json=extended format)
# ============================================================

SAMPLE_DIVIDENDS_RESPONSE = [
    {
        "dividends": [
            {
                "secid": "SBER",
                "registryclosedate": "2024-07-18",
                "value": 33.3,
                "currencyid": "SUR",
            },
            {
                "secid": "SBER",
                "registryclosedate": "2025-07-18",
                "value": 34.84,
                "currencyid": "SUR",
            },
            {
                "secid": "SBER",
                "registryclosedate": "2027-07-18",
                "value": 40.0,
                "currencyid": "SUR",
            },
        ]
    }
]

SAMPLE_DIVIDENDS_WITH_USD = [
    {
        "dividends": [
            {
                "secid": "LKOH",
                "registryclosedate": "2024-05-10",
                "value": 498.0,
                "currencyid": "SUR",
            },
            {
                "secid": "LKOH",
                "registryclosedate": "2024-12-20",
                "value": 514.0,
                "currencyid": "SUR",
            },
        ]
    }
]

EMPTY_DIVIDENDS_RESPONSE = [{"dividends": []}]

NO_DIVIDENDS_RESPONSE = [{}]


# ============================================================
# Unit tests: parsing
# ============================================================


def test_parse_dividends():
    result = parse_dividends(SAMPLE_DIVIDENDS_RESPONSE)
    assert len(result) == 3
    assert result[0]["record_date"] == date(2024, 7, 18)
    assert result[0]["amount"] == 33.3
    assert result[0]["currency"] == "RUB"
    assert result[1]["record_date"] == date(2025, 7, 18)
    assert result[1]["amount"] == 34.84


def test_parse_dividends_empty():
    assert parse_dividends(EMPTY_DIVIDENDS_RESPONSE) == []
    assert parse_dividends(NO_DIVIDENDS_RESPONSE) == []
    assert parse_dividends([]) == []
    assert parse_dividends(None) == []


def test_parse_dividends_skips_invalid():
    data = [
        {
            "dividends": [
                {"registryclosedate": "", "value": 10.0, "currencyid": "SUR"},  # no date
                {"registryclosedate": "2024-01-01", "value": 0, "currencyid": "SUR"},  # zero value
                {"registryclosedate": "2024-05-10", "value": 100.0, "currencyid": "SUR"},  # valid
            ]
        }
    ]
    result = parse_dividends(data)
    assert len(result) == 1
    assert result[0]["amount"] == 100.0


def test_parse_dividends_currency_mapping():
    data = [
        {
            "dividends": [
                {"registryclosedate": "2024-01-01", "value": 10.0, "currencyid": "SUR"},
                {"registryclosedate": "2024-02-01", "value": 5.0, "currencyid": "USD"},
                {"registryclosedate": "2024-03-01", "value": 8.0, "currencyid": ""},
            ]
        }
    ]
    result = parse_dividends(data)
    assert result[0]["currency"] == "RUB"
    assert result[1]["currency"] == "USD"
    assert result[2]["currency"] == "RUB"


# ============================================================
# Integration tests: run_fetch_events
# ============================================================


def _mock_response(json_data):
    """Create a mock httpx.Response."""
    request = httpx.Request("GET", "http://mock")
    return httpx.Response(200, json=json_data, request=request)


@pytest.mark.asyncio
async def test_run_fetch_events(db_session):
    company = Company(ticker="SBER", name="Sberbank")
    db_session.add(company)
    await db_session.commit()

    async def mock_get(self, url, **kwargs):
        return _mock_response(SAMPLE_DIVIDENDS_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_events(db_session, "SBER")

    assert result["ticker"] == "SBER"
    assert result["dividends"] == 3
    assert result["errors"] == []

    # Verify data in DB
    stmt = select(Dividend).where(Dividend.company_id == company.id).order_by(Dividend.record_date)
    dividends = (await db_session.execute(stmt)).scalars().all()
    assert len(dividends) == 3

    # Past dividend should be "paid"
    d1 = dividends[0]
    assert d1.record_date == date(2024, 7, 18)
    assert d1.amount == Decimal("33.3")
    assert d1.currency == "RUB"
    assert d1.status == DividendStatusEnum.paid

    # Future dividend should be "announced"
    d3 = dividends[2]
    assert d3.record_date == date(2027, 7, 18)
    assert d3.status == DividendStatusEnum.announced


@pytest.mark.asyncio
async def test_run_fetch_events_upsert(db_session):
    """Running twice should upsert, not duplicate."""
    company = Company(ticker="SBER", name="Sberbank")
    db_session.add(company)
    await db_session.commit()

    async def mock_get(self, url, **kwargs):
        return _mock_response(SAMPLE_DIVIDENDS_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        await run_fetch_events(db_session, "SBER")
        result = await run_fetch_events(db_session, "SBER")

    assert result["dividends"] == 3

    stmt = select(Dividend).where(Dividend.company_id == company.id)
    dividends = (await db_session.execute(stmt)).scalars().all()
    assert len(dividends) == 3  # No duplicates


@pytest.mark.asyncio
async def test_run_fetch_events_company_not_found(db_session):
    async def mock_get(self, url, **kwargs):
        return _mock_response(SAMPLE_DIVIDENDS_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_events(db_session, "NONEXIST")

    assert "not found" in result["errors"][0]


@pytest.mark.asyncio
async def test_run_fetch_events_no_dividends(db_session):
    company = Company(ticker="VTBR", name="VTB")
    db_session.add(company)
    await db_session.commit()

    async def mock_get(self, url, **kwargs):
        return _mock_response(EMPTY_DIVIDENDS_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_events(db_session, "VTBR")

    assert result["dividends"] == 0
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_run_fetch_events_api_failure(db_session):
    company = Company(ticker="SBER", name="Sberbank")
    db_session.add(company)
    await db_session.commit()

    async def mock_get(self, url, **kwargs):
        raise httpx.ConnectError("Connection refused")

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_events(db_session, "SBER")

    assert result["dividends"] == 0
    assert len(result["errors"]) > 0


# ============================================================
# API endpoint tests
# ============================================================


@pytest.mark.asyncio
async def test_trigger_fetch_events_endpoint(client):
    await client.post(
        "/companies/SBER",
        json={"ticker": "SBER", "name": "Sberbank"},
        headers=HEADERS,
    )

    async def mock_get(self, url, **kwargs):
        return _mock_response(SAMPLE_DIVIDENDS_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        resp = await client.post("/jobs/fetch-events/SBER", headers=HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "SBER"
    assert data["dividends"] == 3


@pytest.mark.asyncio
async def test_trigger_fetch_events_requires_api_key(client):
    resp = await client.post("/jobs/fetch-events/SBER")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_trigger_fetch_events_uppercases_ticker(client):
    await client.post(
        "/companies/LKOH",
        json={"ticker": "LKOH", "name": "ЛУКОЙЛ"},
        headers=HEADERS,
    )

    async def mock_get(self, url, **kwargs):
        return _mock_response(SAMPLE_DIVIDENDS_WITH_USD)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        resp = await client.post("/jobs/fetch-events/lkoh", headers=HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "LKOH"
    assert data["dividends"] == 2
