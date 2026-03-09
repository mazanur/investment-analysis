import pytest

API_KEY = "dev-api-key"
HEADERS = {"X-API-Key": API_KEY}


async def _create_sector(client, slug="finance", name="Finance"):
    resp = await client.post("/sectors", json={"slug": slug, "name": name}, headers=HEADERS)
    return resp.json()


async def _create_company(client, ticker="SBER", name="Sberbank", sector_id=None, **kwargs):
    data = {"ticker": ticker, "name": name, "sector_id": sector_id, **kwargs}
    resp = await client.post(f"/companies/{ticker}", json=data, headers=HEADERS)
    return resp


@pytest.mark.asyncio
async def test_list_companies_empty(client):
    resp = await client.get("/companies")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_company(client):
    resp = await _create_company(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["ticker"] == "SBER"
    assert body["name"] == "Sberbank"
    assert "id" in body
    assert "updated_at" in body


@pytest.mark.asyncio
async def test_create_company_requires_api_key(client):
    resp = await client.post("/companies/SBER", json={"ticker": "SBER", "name": "Sberbank"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upsert_company(client):
    resp1 = await _create_company(client, sentiment="bullish")
    assert resp1.status_code == 201

    resp2 = await _create_company(client, sentiment="bearish")
    assert resp2.status_code == 201
    assert resp2.json()["sentiment"] == "bearish"
    assert resp2.json()["id"] == resp1.json()["id"]  # same record


@pytest.mark.asyncio
async def test_get_company(client):
    await _create_company(client)
    resp = await client.get("/companies/SBER")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ticker"] == "SBER"
    assert body["latest_price"] is None
    assert body["active_catalysts"] == []
    assert body["last_dividend"] is None


@pytest.mark.asyncio
async def test_get_company_not_found(client):
    resp = await client.get("/companies/NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_company(client):
    await _create_company(client)
    resp = await client.put(
        "/companies/SBER", json={"sentiment": "bullish", "current_price": "300.50"}, headers=HEADERS
    )
    assert resp.status_code == 200
    assert resp.json()["sentiment"] == "bullish"
    assert resp.json()["current_price"] == "300.50"


@pytest.mark.asyncio
async def test_update_company_not_found(client):
    resp = await client.put("/companies/NONEXISTENT", json={"name": "X"}, headers=HEADERS)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_company_requires_api_key(client):
    await _create_company(client)
    resp = await client.put("/companies/SBER", json={"name": "Updated"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_filter_by_sentiment(client):
    await _create_company(client, ticker="SBER", name="Sberbank", sentiment="bullish")
    await _create_company(client, ticker="GAZP", name="Gazprom", sentiment="bearish")

    resp = await client.get("/companies?sentiment=bullish")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "SBER"


@pytest.mark.asyncio
async def test_filter_by_position(client):
    await _create_company(client, ticker="SBER", name="Sberbank", position="buy")
    await _create_company(client, ticker="GAZP", name="Gazprom", position="sell")

    resp = await client.get("/companies?position=buy")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "SBER"


@pytest.mark.asyncio
async def test_filter_by_min_upside(client):
    await _create_company(client, ticker="SBER", name="Sberbank", upside="0.5")
    await _create_company(client, ticker="GAZP", name="Gazprom", upside="0.1")

    resp = await client.get("/companies?min_upside=0.3")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "SBER"


@pytest.mark.asyncio
async def test_filter_by_max_p_e(client):
    await _create_company(client, ticker="SBER", name="Sberbank", p_e="5.0")
    await _create_company(client, ticker="GAZP", name="Gazprom", p_e="15.0")

    resp = await client.get("/companies?max_p_e=10")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "SBER"


@pytest.mark.asyncio
async def test_filter_by_sector(client):
    sector = await _create_sector(client, slug="finance", name="Finance")
    await _create_company(client, ticker="SBER", name="Sberbank", sector_id=sector["id"])
    await _create_company(client, ticker="GAZP", name="Gazprom")

    resp = await client.get("/companies?sector=finance")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "SBER"


@pytest.mark.asyncio
async def test_filter_combined(client):
    await _create_company(client, ticker="SBER", name="Sberbank", sentiment="bullish", upside="0.5")
    await _create_company(client, ticker="GAZP", name="Gazprom", sentiment="bullish", upside="0.1")
    await _create_company(client, ticker="LKOH", name="Lukoil", sentiment="bearish", upside="0.6")

    resp = await client.get("/companies?sentiment=bullish&min_upside=0.3")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "SBER"


@pytest.mark.asyncio
async def test_list_companies_ordered_by_ticker(client):
    await _create_company(client, ticker="SBER", name="Sberbank")
    await _create_company(client, ticker="GAZP", name="Gazprom")

    resp = await client.get("/companies")
    tickers = [c["ticker"] for c in resp.json()]
    assert tickers == ["GAZP", "SBER"]


@pytest.mark.asyncio
async def test_create_company_with_sector(client):
    sector = await _create_sector(client)
    resp = await _create_company(client, sector_id=sector["id"])
    assert resp.status_code == 201
    assert resp.json()["sector_id"] == sector["id"]


@pytest.mark.asyncio
async def test_create_company_full_fields(client):
    resp = await _create_company(
        client,
        ticker="SBER",
        name="Sberbank",
        sentiment="bullish",
        position="buy",
        my_fair_value="400.00",
        current_price="300.00",
        upside="0.33",
        market_cap="6000000.00",
        p_e="4.50",
        p_bv="1.20",
        dividend_yield="12.00",
        roe="25.00",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["sentiment"] == "bullish"
    assert body["position"] == "buy"
    assert body["my_fair_value"] == "400.00"
    assert body["current_price"] == "300.00"
    assert body["p_e"] == "4.50"
