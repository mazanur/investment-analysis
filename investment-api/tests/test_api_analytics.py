from datetime import UTC, datetime, timedelta

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


# --- top-upside ---


@pytest.mark.asyncio
async def test_top_upside_empty(client):
    resp = await client.get("/analytics/top-upside")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_top_upside_returns_sorted(client):
    sector = await _create_sector(client)
    await _create_company(
        client, ticker="SBER", name="Sberbank", sector_id=sector["id"],
        upside="0.30", sentiment="bullish",
    )
    await _create_company(
        client, ticker="GAZP", name="Gazprom", sector_id=sector["id"],
        upside="0.60", sentiment="neutral",
    )
    await _create_company(
        client, ticker="LKOH", name="Lukoil",
        upside="0.45", sentiment="bullish",
    )
    # Company without upside — should not appear
    await _create_company(client, ticker="MGNT", name="Magnit")

    resp = await client.get("/analytics/top-upside")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    assert data[0]["ticker"] == "GAZP"
    assert data[0]["upside"] == "0.6000"
    assert data[1]["ticker"] == "LKOH"
    assert data[2]["ticker"] == "SBER"
    # GAZP has sector, LKOH does not
    assert data[0]["sector_slug"] == "finance"
    assert data[1]["sector_slug"] is None


@pytest.mark.asyncio
async def test_top_upside_respects_limit(client):
    await _create_company(client, ticker="SBER", name="Sberbank", upside="0.30")
    await _create_company(client, ticker="GAZP", name="Gazprom", upside="0.60")
    await _create_company(client, ticker="LKOH", name="Lukoil", upside="0.45")

    resp = await client.get("/analytics/top-upside?limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["ticker"] == "GAZP"
    assert data[1]["ticker"] == "LKOH"


# --- screener ---


@pytest.mark.asyncio
async def test_screener_no_filters(client):
    await _create_company(client, ticker="SBER", name="Sberbank", sentiment="bullish")
    await _create_company(client, ticker="GAZP", name="Gazprom", sentiment="bearish")

    resp = await client.get("/analytics/screener")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_screener_filter_by_sentiment(client):
    await _create_company(client, ticker="SBER", name="Sberbank", sentiment="bullish")
    await _create_company(client, ticker="GAZP", name="Gazprom", sentiment="bearish")

    resp = await client.get("/analytics/screener?sentiment=bullish")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "SBER"


@pytest.mark.asyncio
async def test_screener_filter_by_sector(client):
    s1 = await _create_sector(client, slug="finance", name="Finance")
    s2 = await _create_sector(client, slug="oil", name="Oil & Gas")
    await _create_company(client, ticker="SBER", name="Sberbank", sector_id=s1["id"])
    await _create_company(client, ticker="LKOH", name="Lukoil", sector_id=s2["id"])

    resp = await client.get("/analytics/screener?sector=finance")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "SBER"
    assert data[0]["sector_slug"] == "finance"


@pytest.mark.asyncio
async def test_screener_combined_filters(client):
    sector = await _create_sector(client)
    await _create_company(
        client, ticker="SBER", name="Sberbank", sector_id=sector["id"],
        sentiment="bullish", upside="0.40", p_e="5.0", dividend_yield="12.0",
    )
    await _create_company(
        client, ticker="GAZP", name="Gazprom", sector_id=sector["id"],
        sentiment="bullish", upside="0.20", p_e="3.0", dividend_yield="8.0",
    )
    await _create_company(
        client, ticker="LKOH", name="Lukoil",
        sentiment="bearish", upside="0.50", p_e="4.0", dividend_yield="15.0",
    )

    # bullish + min_upside 0.3 → only SBER
    resp = await client.get("/analytics/screener?sentiment=bullish&min_upside=0.3")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "SBER"

    # max_p_e=4 → GAZP and LKOH
    resp = await client.get("/analytics/screener?max_p_e=4")
    data = resp.json()
    assert len(data) == 2

    # min_dividend_yield=10 → SBER and LKOH
    resp = await client.get("/analytics/screener?min_dividend_yield=10")
    data = resp.json()
    assert len(data) == 2
    tickers = {item["ticker"] for item in data}
    assert tickers == {"SBER", "LKOH"}


@pytest.mark.asyncio
async def test_screener_empty_result(client):
    await _create_company(client, ticker="SBER", name="Sberbank", sentiment="bullish")

    resp = await client.get("/analytics/screener?sentiment=bearish")
    assert resp.status_code == 200
    assert resp.json() == []


# --- sector-summary ---


@pytest.mark.asyncio
async def test_sector_summary_empty(client):
    resp = await client.get("/analytics/sector-summary")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_sector_summary(client):
    s1 = await _create_sector(client, slug="finance", name="Finance")
    s2 = await _create_sector(client, slug="oil", name="Oil & Gas")

    await _create_company(
        client, ticker="SBER", name="Sberbank", sector_id=s1["id"],
        sentiment="bullish", upside="0.40",
    )
    await _create_company(
        client, ticker="VTBR", name="VTB", sector_id=s1["id"],
        sentiment="bearish", upside="0.10",
    )
    await _create_company(
        client, ticker="LKOH", name="Lukoil", sector_id=s2["id"],
        sentiment="bullish", upside="0.60",
    )

    resp = await client.get("/analytics/sector-summary")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    finance = next(s for s in data if s["slug"] == "finance")
    assert finance["company_count"] == 2
    assert finance["bullish_count"] == 1
    assert finance["bearish_count"] == 1
    assert finance["neutral_count"] == 0
    assert finance["avg_upside"] is not None

    oil = next(s for s in data if s["slug"] == "oil")
    assert oil["company_count"] == 1
    assert oil["bullish_count"] == 1


@pytest.mark.asyncio
async def test_sector_summary_excludes_unassigned(client):
    """Companies without a sector should not appear in sector summary."""
    await _create_sector(client, slug="finance", name="Finance")
    await _create_company(client, ticker="SBER", name="Sberbank")  # no sector_id

    resp = await client.get("/analytics/sector-summary")
    data = resp.json()
    # finance sector exists but has no companies assigned
    assert len(data) == 0


# --- overdue ---


@pytest.mark.asyncio
async def test_overdue_empty(client):
    resp = await client.get("/analytics/overdue")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_overdue_with_threshold(client):
    await _create_company(client, ticker="SBER", name="Sberbank")
    await _create_company(client, ticker="GAZP", name="Gazprom")

    # Both just created, so days_since_update = 0
    # Default threshold is 90 days, so nothing should be overdue
    resp = await client.get("/analytics/overdue")
    data = resp.json()
    assert len(data) == 0

    # With threshold=0, everything is overdue
    resp = await client.get("/analytics/overdue?days=0")
    data = resp.json()
    assert len(data) == 2

    for item in data:
        assert "ticker" in item
        assert "days_since_update" in item
        assert "updated_at" in item


@pytest.mark.asyncio
async def test_overdue_returns_sector_slug(client):
    sector = await _create_sector(client)
    await _create_company(client, ticker="SBER", name="Sberbank", sector_id=sector["id"])

    resp = await client.get("/analytics/overdue?days=0")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["sector_slug"] == "finance"
