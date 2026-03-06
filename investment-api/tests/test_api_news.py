import pytest

API_KEY = "dev-api-key"
HEADERS = {"X-API-Key": API_KEY}


async def _create_sector(client, slug="finance", name="Finance"):
    resp = await client.post(f"/sectors", json={"slug": slug, "name": name}, headers=HEADERS)
    return resp.json()


async def _create_company(client, ticker="SBER", name="Sberbank"):
    resp = await client.post(f"/companies/{ticker}", json={"ticker": ticker, "name": name}, headers=HEADERS)
    return resp.json()


async def _create_news(client, **kwargs):
    data = {
        "date": "2026-03-01",
        "title": "Test news",
        **kwargs,
    }
    return await client.post("/news", json=data, headers=HEADERS)


@pytest.mark.asyncio
async def test_create_news_minimal(client):
    resp = await _create_news(client, title="Macro news without company")
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Macro news without company"
    assert body["company_id"] is None
    assert body["sector_id"] is None
    assert "id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_create_news_with_company(client):
    company = await _create_company(client)
    resp = await _create_news(
        client,
        company_id=company["id"],
        title="Sberbank reports Q4 earnings",
        impact="positive",
        strength="high",
        source="MOEX",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["company_id"] == company["id"]
    assert body["impact"] == "positive"
    assert body["strength"] == "high"
    assert body["source"] == "MOEX"


@pytest.mark.asyncio
async def test_create_news_with_sector(client):
    sector = await _create_sector(client)
    resp = await _create_news(
        client,
        sector_id=sector["id"],
        title="Banking sector regulation update",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["sector_id"] == sector["id"]


@pytest.mark.asyncio
async def test_create_news_invalid_company(client):
    resp = await _create_news(client, company_id=99999, title="Bad ref")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_news_invalid_sector(client):
    resp = await _create_news(client, sector_id=99999, title="Bad ref")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_news_requires_api_key(client):
    resp = await client.post("/news", json={"date": "2026-03-01", "title": "test"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_news_invalid_api_key(client):
    resp = await client.post(
        "/news",
        json={"date": "2026-03-01", "title": "test"},
        headers={"X-API-Key": "wrong"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_company_news(client):
    company = await _create_company(client)
    await _create_news(client, company_id=company["id"], title="News 1", date="2026-03-01")
    await _create_news(client, company_id=company["id"], title="News 2", date="2026-03-02")

    resp = await client.get("/companies/SBER/news")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Ordered by date desc
    assert data[0]["title"] == "News 2"
    assert data[1]["title"] == "News 1"


@pytest.mark.asyncio
async def test_list_company_news_not_found(client):
    resp = await client.get("/companies/NONEXISTENT/news")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_sector_news(client):
    sector = await _create_sector(client)
    await _create_news(client, sector_id=sector["id"], title="Sector news")

    resp = await client.get("/sectors/finance/news")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Sector news"


@pytest.mark.asyncio
async def test_list_sector_news_not_found(client):
    resp = await client.get("/sectors/nonexistent/news")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_all_news(client):
    await _create_news(client, title="News A", date="2026-03-01")
    await _create_news(client, title="News B", date="2026-03-02")

    resp = await client.get("/news")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_filter_news_by_impact(client):
    await _create_news(client, title="Good news", impact="positive")
    await _create_news(client, title="Bad news", impact="negative")

    resp = await client.get("/news?impact=positive")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Good news"


@pytest.mark.asyncio
async def test_filter_news_by_date_range(client):
    await _create_news(client, title="Old", date="2026-01-01")
    await _create_news(client, title="Mid", date="2026-02-15")
    await _create_news(client, title="New", date="2026-03-01")

    resp = await client.get("/news?from=2026-02-01&to=2026-02-28")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Mid"


@pytest.mark.asyncio
async def test_update_news(client):
    create_resp = await _create_news(client, title="Original")
    news_id = create_resp.json()["id"]

    resp = await client.put(
        f"/news/{news_id}",
        json={"impact": "negative", "summary": "Updated summary"},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["impact"] == "negative"
    assert body["summary"] == "Updated summary"
    assert body["title"] == "Original"  # unchanged


@pytest.mark.asyncio
async def test_update_news_not_found(client):
    resp = await client.put(
        "/news/99999",
        json={"impact": "positive"},
        headers=HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_news_requires_api_key(client):
    create_resp = await _create_news(client, title="test")
    news_id = create_resp.json()["id"]
    resp = await client.put(f"/news/{news_id}", json={"impact": "positive"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_news_ordered_by_date_desc(client):
    await _create_news(client, title="First", date="2026-01-01")
    await _create_news(client, title="Second", date="2026-02-01")
    await _create_news(client, title="Third", date="2026-03-01")

    resp = await client.get("/news")
    titles = [n["title"] for n in resp.json()]
    assert titles == ["Third", "Second", "First"]
