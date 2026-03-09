"""
Tests for MOEX data fetching jobs.

Uses mocked MOEX API responses to test parsing and DB writing logic.

Author: AlmazNurmukhametov
"""

from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import select

from app.jobs.fetch_moex import (
    _calculate_adv,
    _parse_candles,
    _parse_tqbr_all,
    run_fetch_moex,
)
from app.jobs.fetch_prices import (
    _parse_candles as parse_price_candles,
    _parse_tqbr_snapshot,
    run_fetch_prices,
)
from app.models import Company, Price

API_KEY = "dev-api-key"
HEADERS = {"X-API-Key": API_KEY}


# ============================================================
# Sample MOEX ISS API responses (iss.json=extended format)
# ============================================================

SAMPLE_TQBR_RESPONSE = [
    {
        "securities": [
            {"SECID": "SBER", "ISSUESIZE": 21586948000, "SHORTNAME": "Сбербанк"},
            {"SECID": "LKOH", "ISSUESIZE": 654007191, "SHORTNAME": "ЛУКОЙЛ"},
        ],
        "marketdata": [
            {
                "SECID": "SBER",
                "LAST": 280.50,
                "OPEN": 278.00,
                "HIGH": 282.00,
                "LOW": 277.00,
                "VALTODAY": 5000000000,
                "ISSUECAPITALIZATION": 6050000000000,
                "BID": 280.40,
                "OFFER": 280.60,
            },
            {
                "SECID": "LKOH",
                "LAST": 7500.00,
                "OPEN": 7480.00,
                "HIGH": 7550.00,
                "LOW": 7460.00,
                "VALTODAY": 3000000000,
                "ISSUECAPITALIZATION": 4900000000000,
                "BID": 7498.00,
                "OFFER": 7502.00,
            },
        ],
    }
]

SAMPLE_CANDLES_RESPONSE = [
    {
        "candles": [
            {
                "begin": "2026-03-03 00:00:00",
                "open": 275.0,
                "close": 278.5,
                "high": 280.0,
                "low": 274.0,
                "value": 4500000000,
                "volume": 16000000,
            },
            {
                "begin": "2026-03-04 00:00:00",
                "open": 278.5,
                "close": 280.0,
                "high": 281.0,
                "low": 277.5,
                "value": 5200000000,
                "volume": 18500000,
            },
            {
                "begin": "2026-03-05 00:00:00",
                "open": 280.0,
                "close": 280.5,
                "high": 282.0,
                "low": 279.0,
                "value": 4800000000,
                "volume": 17000000,
            },
        ]
    }
]

EMPTY_CANDLES_RESPONSE = [{"candles": []}]


# ============================================================
# Unit tests: parsing functions
# ============================================================


def test_parse_tqbr_all():
    result = _parse_tqbr_all(SAMPLE_TQBR_RESPONSE)
    assert "SBER" in result
    assert "LKOH" in result
    assert result["SBER"]["last"] == 280.50
    assert result["SBER"]["issuecap"] == 6050000000000
    assert result["SBER"]["issuesize"] == 21586948000
    assert result["LKOH"]["last"] == 7500.00


def test_parse_tqbr_all_empty():
    assert _parse_tqbr_all([]) == {}
    assert _parse_tqbr_all(None) == {}
    assert _parse_tqbr_all([{}]) == {}


def test_parse_tqbr_snapshot():
    result = _parse_tqbr_snapshot(SAMPLE_TQBR_RESPONSE)
    assert "SBER" in result
    assert result["SBER"]["last"] == 280.50


def test_parse_candles():
    result = _parse_candles(SAMPLE_CANDLES_RESPONSE)
    assert len(result) == 3
    assert result[0]["date"] == "2026-03-03"
    assert result[0]["open"] == 275.0
    assert result[0]["close"] == 278.5
    assert result[0]["high"] == 280.0
    assert result[0]["low"] == 274.0
    assert result[0]["value"] == 4500000000


def test_parse_price_candles():
    result = parse_price_candles(SAMPLE_CANDLES_RESPONSE)
    assert len(result) == 3
    assert result[0]["date"] == "2026-03-03"
    assert result[0]["volume_rub"] == 4500000000


def test_parse_candles_empty():
    assert _parse_candles([]) == []
    assert _parse_candles(None) == []
    assert _parse_candles(EMPTY_CANDLES_RESPONSE) == []


def test_calculate_adv():
    candles = [
        {"value": 4500000000},
        {"value": 5200000000},
        {"value": 4800000000},
    ]
    adv = _calculate_adv(candles, 30)
    assert adv == pytest.approx((4500000000 + 5200000000 + 4800000000) / 3)


def test_calculate_adv_filters_zero_volume():
    candles = [
        {"value": 4500000000},
        {"value": 0},
        {"value": 4800000000},
    ]
    adv = _calculate_adv(candles, 30)
    assert adv == pytest.approx((4500000000 + 4800000000) / 2)


def test_calculate_adv_empty():
    assert _calculate_adv([], 30) == 0


def test_calculate_adv_respects_days_limit():
    candles = [{"value": 1000} for _ in range(50)]
    candles[-1]["value"] = 5000  # last one is different
    adv = _calculate_adv(candles, 3)
    # Takes last 3: [1000, 1000, 5000]
    assert adv == pytest.approx((1000 + 1000 + 5000) / 3)


# ============================================================
# Integration tests: fetch_moex job
# ============================================================


def _mock_response(json_data):
    """Create a mock httpx.Response with a request set (needed for raise_for_status)."""
    request = httpx.Request("GET", "http://mock")
    response = httpx.Response(200, json=json_data, request=request)
    return response


@pytest.mark.asyncio
async def test_run_fetch_moex(db_session):
    # Create companies in DB
    sber = Company(ticker="SBER", name="Sberbank")
    lkoh = Company(ticker="LKOH", name="ЛУКОЙЛ")
    db_session.add_all([sber, lkoh])
    await db_session.commit()

    # Mock httpx.AsyncClient.get to return MOEX data
    call_count = 0

    async def mock_get(self, url, **kwargs):
        nonlocal call_count
        call_count += 1
        if "candles" in url:
            return _mock_response(SAMPLE_CANDLES_RESPONSE)
        return _mock_response(SAMPLE_TQBR_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_moex(db_session)

    assert result["updated"] == 2
    assert result["not_found"] == 0
    assert result["errors"] == []

    # Verify company data was updated
    await db_session.refresh(sber)
    await db_session.refresh(lkoh)
    assert sber.current_price == Decimal("280.50")
    assert sber.market_cap == Decimal("6050000000000")
    assert sber.shares_out == 21586948000
    assert sber.adv_rub_mln is not None
    assert lkoh.current_price == Decimal("7500.00")


@pytest.mark.asyncio
async def test_run_fetch_moex_specific_tickers(db_session):
    sber = Company(ticker="SBER", name="Sberbank")
    lkoh = Company(ticker="LKOH", name="ЛУКОЙЛ")
    db_session.add_all([sber, lkoh])
    await db_session.commit()

    async def mock_get(self, url, **kwargs):
        if "candles" in url:
            return _mock_response(SAMPLE_CANDLES_RESPONSE)
        return _mock_response(SAMPLE_TQBR_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_moex(db_session, tickers=["SBER"])

    assert result["updated"] == 1


@pytest.mark.asyncio
async def test_run_fetch_moex_no_companies(db_session):
    async def mock_get(self, url, **kwargs):
        return _mock_response(SAMPLE_TQBR_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_moex(db_session)

    assert result["updated"] == 0
    assert "No companies found" in result["errors"][0]


@pytest.mark.asyncio
async def test_run_fetch_moex_api_failure(db_session):
    sber = Company(ticker="SBER", name="Sberbank")
    db_session.add(sber)
    await db_session.commit()

    async def mock_get(self, url, **kwargs):
        raise httpx.ConnectError("Connection refused")

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_moex(db_session)

    assert result["updated"] == 0
    assert len(result["errors"]) > 0


@pytest.mark.asyncio
async def test_run_fetch_moex_ticker_not_on_moex(db_session):
    # Company exists in DB but not in MOEX response
    xyz = Company(ticker="XYZ", name="Unknown Corp")
    db_session.add(xyz)
    await db_session.commit()

    async def mock_get(self, url, **kwargs):
        if "candles" in url:
            return _mock_response(EMPTY_CANDLES_RESPONSE)
        return _mock_response(SAMPLE_TQBR_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_moex(db_session)

    assert result["not_found"] == 1
    assert result["updated"] == 0


# ============================================================
# Integration tests: fetch_prices job
# ============================================================


@pytest.mark.asyncio
async def test_run_fetch_prices_snapshot(db_session):
    sber = Company(ticker="SBER", name="Sberbank")
    db_session.add(sber)
    await db_session.commit()

    async def mock_get(self, url, **kwargs):
        return _mock_response(SAMPLE_TQBR_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_prices(db_session)

    assert result["updated"] == 1
    assert result["total_prices"] == 1
    assert result["not_found"] == 0

    # Verify price was written
    stmt = select(Price).where(Price.company_id == sber.id)
    prices_result = await db_session.execute(stmt)
    prices = prices_result.scalars().all()
    assert len(prices) == 1
    assert prices[0].close == Decimal("280.50")
    assert prices[0].open == Decimal("278.00")
    assert prices[0].high == Decimal("282.00")
    assert prices[0].low == Decimal("277.00")


@pytest.mark.asyncio
async def test_run_fetch_prices_backfill(db_session):
    sber = Company(ticker="SBER", name="Sberbank")
    db_session.add(sber)
    await db_session.commit()

    async def mock_get(self, url, **kwargs):
        if "candles" in url:
            return _mock_response(SAMPLE_CANDLES_RESPONSE)
        return _mock_response(SAMPLE_TQBR_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_prices(db_session, backfill_days=30)

    assert result["updated"] == 1
    assert result["total_prices"] == 3  # 3 candles in mock
    assert result["not_found"] == 0

    # Verify prices
    stmt = select(Price).where(Price.company_id == sber.id).order_by(Price.date)
    prices_result = await db_session.execute(stmt)
    prices = prices_result.scalars().all()
    assert len(prices) == 3
    assert prices[0].date.isoformat() == "2026-03-03"
    assert prices[0].close == Decimal("278.50")
    assert prices[2].date.isoformat() == "2026-03-05"
    assert prices[2].close == Decimal("280.50")


@pytest.mark.asyncio
async def test_run_fetch_prices_upsert(db_session):
    """Test that running fetch_prices twice upserts correctly."""
    sber = Company(ticker="SBER", name="Sberbank")
    db_session.add(sber)
    await db_session.commit()

    async def mock_get(self, url, **kwargs):
        if "candles" in url:
            return _mock_response(SAMPLE_CANDLES_RESPONSE)
        return _mock_response(SAMPLE_TQBR_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        await run_fetch_prices(db_session, backfill_days=30)
        # Run again - should upsert, not duplicate
        result = await run_fetch_prices(db_session, backfill_days=30)

    assert result["total_prices"] == 3

    stmt = select(Price).where(Price.company_id == sber.id)
    prices_result = await db_session.execute(stmt)
    prices = prices_result.scalars().all()
    assert len(prices) == 3  # No duplicates


@pytest.mark.asyncio
async def test_run_fetch_prices_no_companies(db_session):
    async def mock_get(self, url, **kwargs):
        return _mock_response(SAMPLE_TQBR_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_prices(db_session)

    assert "No companies found" in result["errors"][0]


@pytest.mark.asyncio
async def test_run_fetch_prices_api_failure(db_session):
    sber = Company(ticker="SBER", name="Sberbank")
    db_session.add(sber)
    await db_session.commit()

    async def mock_get(self, url, **kwargs):
        raise httpx.ConnectError("Connection refused")

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_prices(db_session)

    assert result["updated"] == 0
    assert len(result["errors"]) > 0


@pytest.mark.asyncio
async def test_run_fetch_prices_ticker_not_on_moex(db_session):
    xyz = Company(ticker="XYZ", name="Unknown Corp")
    db_session.add(xyz)
    await db_session.commit()

    async def mock_get(self, url, **kwargs):
        return _mock_response(SAMPLE_TQBR_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        result = await run_fetch_prices(db_session)

    assert result["not_found"] == 1


# ============================================================
# API endpoint tests
# ============================================================


@pytest.mark.asyncio
async def test_trigger_fetch_moex_endpoint(client):
    # Create company first
    await client.post("/companies/SBER", json={"ticker": "SBER", "name": "Sberbank"}, headers=HEADERS)

    async def mock_get(self, url, **kwargs):
        if "candles" in url:
            return _mock_response(SAMPLE_CANDLES_RESPONSE)
        return _mock_response(SAMPLE_TQBR_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        resp = await client.post("/jobs/fetch-moex", headers=HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] == 1


@pytest.mark.asyncio
async def test_trigger_fetch_moex_requires_api_key(client):
    resp = await client.post("/jobs/fetch-moex")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_trigger_fetch_moex_invalid_api_key(client):
    resp = await client.post("/jobs/fetch-moex", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_trigger_fetch_prices_endpoint(client):
    await client.post("/companies/SBER", json={"ticker": "SBER", "name": "Sberbank"}, headers=HEADERS)

    async def mock_get(self, url, **kwargs):
        return _mock_response(SAMPLE_TQBR_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        resp = await client.post("/jobs/fetch-prices", headers=HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] == 1
    assert data["total_prices"] == 1


@pytest.mark.asyncio
async def test_trigger_fetch_prices_backfill_endpoint(client):
    await client.post("/companies/SBER", json={"ticker": "SBER", "name": "Sberbank"}, headers=HEADERS)

    async def mock_get(self, url, **kwargs):
        if "candles" in url:
            return _mock_response(SAMPLE_CANDLES_RESPONSE)
        return _mock_response(SAMPLE_TQBR_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        resp = await client.post("/jobs/fetch-prices?backfill_days=30", headers=HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] == 1
    assert data["total_prices"] == 3


@pytest.mark.asyncio
async def test_trigger_fetch_prices_with_tickers(client):
    await client.post("/companies/SBER", json={"ticker": "SBER", "name": "Sberbank"}, headers=HEADERS)
    await client.post("/companies/LKOH", json={"ticker": "LKOH", "name": "ЛУКОЙЛ"}, headers=HEADERS)

    async def mock_get(self, url, **kwargs):
        return _mock_response(SAMPLE_TQBR_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        resp = await client.post("/jobs/fetch-prices?tickers=SBER", headers=HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] == 1  # Only SBER


@pytest.mark.asyncio
async def test_trigger_fetch_prices_requires_api_key(client):
    resp = await client.post("/jobs/fetch-prices")
    assert resp.status_code == 422
