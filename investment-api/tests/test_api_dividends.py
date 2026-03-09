import datetime as dt

import pytest

API_KEY = "dev-api-key"
HEADERS = {"X-API-Key": API_KEY}


async def _create_company(client, ticker="SBER", name="Sberbank"):
    resp = await client.post(f"/companies/{ticker}", json={"ticker": ticker, "name": name}, headers=HEADERS)
    return resp.json()


async def _create_dividend(client, ticker="SBER", record_date="2025-07-15", amount="33.30", **kwargs):
    data = {"record_date": record_date, "amount": amount, **kwargs}
    return await client.post(f"/companies/{ticker}/dividends", json=data, headers=HEADERS)


@pytest.mark.asyncio
async def test_list_dividends_empty(client):
    await _create_company(client)
    resp = await client.get("/companies/SBER/dividends")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_dividends_company_not_found(client):
    resp = await client.get("/companies/NONEXISTENT/dividends")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_dividend(client):
    await _create_company(client)
    resp = await _create_dividend(client, amount="33.30", period_label="2024H2")
    assert resp.status_code == 201
    body = resp.json()
    assert body["record_date"] == "2025-07-15"
    assert body["amount"] == "33.30"
    assert body["currency"] == "RUB"
    assert body["status"] == "announced"
    assert body["period_label"] == "2024H2"
    assert "id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_create_dividend_requires_api_key(client):
    await _create_company(client)
    resp = await client.post(
        "/companies/SBER/dividends",
        json={"record_date": "2025-07-15", "amount": "33.30"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_dividend_invalid_api_key(client):
    await _create_company(client)
    resp = await client.post(
        "/companies/SBER/dividends",
        json={"record_date": "2025-07-15", "amount": "33.30"},
        headers={"X-API-Key": "wrong"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_dividend_company_not_found(client):
    resp = await _create_dividend(client, ticker="NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_dividends_ordered_by_date_desc(client):
    await _create_company(client)
    await _create_dividend(client, record_date="2025-01-15")
    await _create_dividend(client, record_date="2025-07-15")
    await _create_dividend(client, record_date="2025-04-15")

    resp = await client.get("/companies/SBER/dividends")
    dates = [d["record_date"] for d in resp.json()]
    assert dates == ["2025-07-15", "2025-04-15", "2025-01-15"]


@pytest.mark.asyncio
async def test_create_dividend_with_all_fields(client):
    await _create_company(client)
    resp = await _create_dividend(
        client,
        record_date="2025-07-15",
        amount="33.30",
        currency="RUB",
        yield_pct="12.50",
        period_label="2024H2",
        status="confirmed",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["yield_pct"] == "12.50"
    assert body["status"] == "confirmed"


@pytest.mark.asyncio
async def test_upcoming_dividends_empty(client):
    resp = await client.get("/dividends/upcoming")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_upcoming_dividends(client):
    await _create_company(client, ticker="SBER", name="Sberbank")
    await _create_company(client, ticker="GAZP", name="Gazprom")

    # Future dates
    future1 = (dt.date.today() + dt.timedelta(days=30)).isoformat()
    future2 = (dt.date.today() + dt.timedelta(days=60)).isoformat()
    # Past date
    past = (dt.date.today() - dt.timedelta(days=30)).isoformat()

    await _create_dividend(client, ticker="SBER", record_date=future1, amount="33.30")
    await _create_dividend(client, ticker="GAZP", record_date=future2, amount="15.00")
    await _create_dividend(client, ticker="SBER", record_date=past, amount="20.00")

    resp = await client.get("/dividends/upcoming")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Ordered by record_date ascending (nearest first)
    assert data[0]["record_date"] == future1
    assert data[1]["record_date"] == future2


@pytest.mark.asyncio
async def test_upcoming_dividends_with_limit(client):
    await _create_company(client, ticker="SBER", name="Sberbank")

    future1 = (dt.date.today() + dt.timedelta(days=30)).isoformat()
    future2 = (dt.date.today() + dt.timedelta(days=60)).isoformat()

    await _create_dividend(client, ticker="SBER", record_date=future1, amount="33.30")
    await _create_dividend(client, ticker="SBER", record_date=future2, amount="20.00")

    resp = await client.get("/dividends/upcoming?limit=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["record_date"] == future1


@pytest.mark.asyncio
async def test_upcoming_dividends_excludes_past(client):
    await _create_company(client)
    past = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    await _create_dividend(client, record_date=past, amount="33.30")

    resp = await client.get("/dividends/upcoming")
    assert resp.status_code == 200
    assert resp.json() == []
