import pytest

API_KEY = "dev-api-key"
HEADERS = {"X-API-Key": API_KEY}


@pytest.mark.asyncio
async def test_list_sectors_empty(client):
    resp = await client.get("/sectors")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_sector(client):
    data = {"slug": "finance", "name": "Finance", "description": "Financial sector"}
    resp = await client.post("/sectors", json=data, headers=HEADERS)
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "finance"
    assert body["name"] == "Finance"
    assert body["description"] == "Financial sector"
    assert "id" in body
    assert "updated_at" in body


@pytest.mark.asyncio
async def test_create_sector_requires_api_key(client):
    data = {"slug": "finance", "name": "Finance"}
    resp = await client.post("/sectors", json=data)
    assert resp.status_code == 422  # missing header


@pytest.mark.asyncio
async def test_create_sector_invalid_api_key(client):
    data = {"slug": "finance", "name": "Finance"}
    resp = await client.post("/sectors", json=data, headers={"X-API-Key": "wrong-key"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_sector_duplicate_slug(client):
    data = {"slug": "tech", "name": "Technology"}
    resp = await client.post("/sectors", json=data, headers=HEADERS)
    assert resp.status_code == 201

    resp = await client.post("/sectors", json=data, headers=HEADERS)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_sector_by_slug(client):
    data = {"slug": "oil", "name": "Oil & Gas"}
    await client.post("/sectors", json=data, headers=HEADERS)

    resp = await client.get("/sectors/oil")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "oil"
    assert resp.json()["name"] == "Oil & Gas"


@pytest.mark.asyncio
async def test_get_sector_not_found(client):
    resp = await client.get("/sectors/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_sector(client):
    await client.post("/sectors", json={"slug": "metals", "name": "Metals"}, headers=HEADERS)

    resp = await client.put("/sectors/metals", json={"name": "Metals & Mining"}, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Metals & Mining"
    assert resp.json()["slug"] == "metals"


@pytest.mark.asyncio
async def test_update_sector_not_found(client):
    resp = await client.put("/sectors/nonexistent", json={"name": "X"}, headers=HEADERS)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_sector_requires_api_key(client):
    await client.post("/sectors", json={"slug": "retail", "name": "Retail"}, headers=HEADERS)
    resp = await client.put("/sectors/retail", json={"name": "Retail Updated"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_sectors_ordered(client):
    await client.post("/sectors", json={"slug": "z-sector", "name": "Zebra"}, headers=HEADERS)
    await client.post("/sectors", json={"slug": "a-sector", "name": "Alpha"}, headers=HEADERS)

    resp = await client.get("/sectors")
    names = [s["name"] for s in resp.json()]
    assert names == ["Alpha", "Zebra"]
