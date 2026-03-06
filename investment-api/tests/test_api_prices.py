import pytest

API_KEY = "dev-api-key"
HEADERS = {"X-API-Key": API_KEY}


async def _create_company(client, ticker="SBER", name="Sberbank"):
    resp = await client.post(f"/companies/{ticker}", json={"ticker": ticker, "name": name}, headers=HEADERS)
    return resp.json()


async def _bulk_create_prices(client, ticker="SBER", prices=None):
    if prices is None:
        prices = [
            {"date": "2026-03-03", "close": "280.50", "open": "278.00", "high": "282.00", "low": "277.00"},
            {"date": "2026-03-04", "close": "283.10", "open": "280.50", "high": "285.00", "low": "279.50"},
            {"date": "2026-03-05", "close": "281.00", "open": "283.10", "high": "284.00", "low": "280.00"},
        ]
    return await client.post(
        f"/companies/{ticker}/prices",
        json={"prices": prices},
        headers=HEADERS,
    )


@pytest.mark.asyncio
async def test_list_prices_empty(client):
    await _create_company(client)
    resp = await client.get("/companies/SBER/prices")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_prices_company_not_found(client):
    resp = await client.get("/companies/NONEXISTENT/prices")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_bulk_create_prices(client):
    await _create_company(client)
    resp = await _bulk_create_prices(client)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 3
    # All prices should have company_id and id
    for p in data:
        assert "id" in p
        assert "company_id" in p
        assert "created_at" in p


@pytest.mark.asyncio
async def test_bulk_create_prices_requires_api_key(client):
    await _create_company(client)
    resp = await client.post(
        "/companies/SBER/prices",
        json={"prices": [{"date": "2026-03-03", "close": "280.50"}]},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_create_prices_invalid_api_key(client):
    await _create_company(client)
    resp = await client.post(
        "/companies/SBER/prices",
        json={"prices": [{"date": "2026-03-03", "close": "280.50"}]},
        headers={"X-API-Key": "wrong"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_bulk_create_prices_company_not_found(client):
    resp = await _bulk_create_prices(client, ticker="NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_prices_ordered_by_date_desc(client):
    await _create_company(client)
    await _bulk_create_prices(client)

    resp = await client.get("/companies/SBER/prices")
    dates = [p["date"] for p in resp.json()]
    assert dates == ["2026-03-05", "2026-03-04", "2026-03-03"]


@pytest.mark.asyncio
async def test_prices_filter_from_date(client):
    await _create_company(client)
    await _bulk_create_prices(client)

    resp = await client.get("/companies/SBER/prices?from=2026-03-04")
    assert resp.status_code == 200
    dates = [p["date"] for p in resp.json()]
    assert dates == ["2026-03-05", "2026-03-04"]


@pytest.mark.asyncio
async def test_prices_filter_to_date(client):
    await _create_company(client)
    await _bulk_create_prices(client)

    resp = await client.get("/companies/SBER/prices?to=2026-03-04")
    assert resp.status_code == 200
    dates = [p["date"] for p in resp.json()]
    assert dates == ["2026-03-04", "2026-03-03"]


@pytest.mark.asyncio
async def test_prices_filter_date_range(client):
    await _create_company(client)
    await _bulk_create_prices(client)

    resp = await client.get("/companies/SBER/prices?from=2026-03-04&to=2026-03-04")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["date"] == "2026-03-04"


@pytest.mark.asyncio
async def test_get_latest_price(client):
    await _create_company(client)
    await _bulk_create_prices(client)

    resp = await client.get("/companies/SBER/prices/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["date"] == "2026-03-05"
    assert body["close"] == "281.00"


@pytest.mark.asyncio
async def test_get_latest_price_not_found(client):
    await _create_company(client)
    resp = await client.get("/companies/SBER/prices/latest")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_latest_price_company_not_found(client):
    resp = await client.get("/companies/NONEXISTENT/prices/latest")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_bulk_upsert_prices_updates_existing(client):
    await _create_company(client)
    # Create initial prices
    await _bulk_create_prices(client, prices=[
        {"date": "2026-03-03", "close": "280.50"},
        {"date": "2026-03-04", "close": "283.10"},
    ])

    # Upsert: update one, add one new
    resp = await _bulk_create_prices(client, prices=[
        {"date": "2026-03-03", "close": "290.00"},  # Updated
        {"date": "2026-03-05", "close": "295.00"},  # New
    ])
    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 2

    # Check all prices
    resp = await client.get("/companies/SBER/prices")
    data = resp.json()
    assert len(data) == 3

    prices_by_date = {p["date"]: p["close"] for p in data}
    assert prices_by_date["2026-03-03"] == "290.00"  # Updated
    assert prices_by_date["2026-03-04"] == "283.10"  # Unchanged
    assert prices_by_date["2026-03-05"] == "295.00"  # New


@pytest.mark.asyncio
async def test_price_with_volume_and_market_cap(client):
    await _create_company(client)
    resp = await _bulk_create_prices(client, prices=[
        {
            "date": "2026-03-03",
            "close": "280.50",
            "open": "278.00",
            "high": "282.00",
            "low": "277.00",
            "volume_rub": "5000000000.00",
            "market_cap": "6500000000000.00",
        },
    ])
    assert resp.status_code == 201
    body = resp.json()[0]
    assert body["volume_rub"] == "5000000000.00"
    assert body["market_cap"] == "6500000000000.00"


@pytest.mark.asyncio
async def test_price_minimal_fields(client):
    await _create_company(client)
    resp = await _bulk_create_prices(client, prices=[
        {"date": "2026-03-03", "close": "280.50"},
    ])
    assert resp.status_code == 201
    body = resp.json()[0]
    assert body["close"] == "280.50"
    assert body["open"] is None
    assert body["high"] is None
    assert body["low"] is None
    assert body["volume_rub"] is None
    assert body["market_cap"] is None
