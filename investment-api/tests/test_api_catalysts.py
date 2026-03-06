import pytest

API_KEY = "dev-api-key"
HEADERS = {"X-API-Key": API_KEY}


async def _create_company(client, ticker="SBER", name="Sberbank"):
    resp = await client.post(f"/companies/{ticker}", json={"ticker": ticker, "name": name}, headers=HEADERS)
    return resp.json()


async def _create_catalyst(client, ticker="SBER", **kwargs):
    data = {
        "type": "opportunity",
        "impact": "positive",
        "magnitude": "medium",
        "description": "Test catalyst",
        **kwargs,
    }
    return await client.post(f"/companies/{ticker}/catalysts", json=data, headers=HEADERS)


@pytest.mark.asyncio
async def test_list_catalysts_empty(client):
    await _create_company(client)
    resp = await client.get("/companies/SBER/catalysts")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_catalysts_company_not_found(client):
    resp = await client.get("/companies/NONEXISTENT/catalysts")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_company_catalyst(client):
    await _create_company(client)
    resp = await _create_catalyst(
        client,
        description="Strong dividend growth expected",
        source="analyst report",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["type"] == "opportunity"
    assert body["impact"] == "positive"
    assert body["magnitude"] == "medium"
    assert body["description"] == "Strong dividend growth expected"
    assert body["source"] == "analyst report"
    assert body["is_active"] is True
    assert body["company_id"] is not None
    assert "id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_create_catalyst_requires_api_key(client):
    await _create_company(client)
    resp = await client.post(
        "/companies/SBER/catalysts",
        json={"type": "risk", "impact": "negative", "description": "test"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_catalyst_invalid_api_key(client):
    await _create_company(client)
    resp = await client.post(
        "/companies/SBER/catalysts",
        json={"type": "risk", "impact": "negative", "description": "test"},
        headers={"X-API-Key": "wrong"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_catalyst_company_not_found(client):
    resp = await _create_catalyst(client, ticker="NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_macro_catalyst(client):
    data = {
        "type": "cb_meeting",
        "impact": "mixed",
        "magnitude": "high",
        "description": "CB rate decision meeting",
        "date": "2026-03-21",
    }
    resp = await client.post("/catalysts", json=data, headers=HEADERS)
    assert resp.status_code == 201
    body = resp.json()
    assert body["company_id"] is None
    assert body["type"] == "cb_meeting"
    assert body["date"] == "2026-03-21"
    assert body["magnitude"] == "high"


@pytest.mark.asyncio
async def test_create_macro_catalyst_requires_api_key(client):
    data = {
        "type": "cb_meeting",
        "impact": "mixed",
        "description": "CB rate decision meeting",
    }
    resp = await client.post("/catalysts", json=data)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_filter_catalysts_by_active(client):
    await _create_company(client)
    # Create active catalyst
    await _create_catalyst(client, description="Active one", is_active=True)
    # Create inactive catalyst
    await _create_catalyst(client, description="Inactive one", is_active=False)

    # Filter active only
    resp = await client.get("/companies/SBER/catalysts?is_active=true")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["description"] == "Active one"

    # Filter inactive only
    resp = await client.get("/companies/SBER/catalysts?is_active=false")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["description"] == "Inactive one"

    # No filter — all catalysts
    resp = await client.get("/companies/SBER/catalysts")
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_update_catalyst_deactivate(client):
    await _create_company(client)
    create_resp = await _create_catalyst(client, description="Will be deactivated")
    catalyst_id = create_resp.json()["id"]

    resp = await client.put(
        f"/catalysts/{catalyst_id}",
        json={"is_active": False},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_active"] is False
    assert body["expired_at"] is not None


@pytest.mark.asyncio
async def test_update_catalyst_not_found(client):
    resp = await client.put(
        "/catalysts/99999",
        json={"is_active": False},
        headers=HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_catalyst_fields(client):
    await _create_company(client)
    create_resp = await _create_catalyst(client, description="Original")
    catalyst_id = create_resp.json()["id"]

    resp = await client.put(
        f"/catalysts/{catalyst_id}",
        json={"description": "Updated", "magnitude": "high"},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["description"] == "Updated"
    assert body["magnitude"] == "high"
    # Still active, no expired_at
    assert body["is_active"] is True
    assert body["expired_at"] is None


@pytest.mark.asyncio
async def test_update_catalyst_requires_api_key(client):
    await _create_company(client)
    create_resp = await _create_catalyst(client)
    catalyst_id = create_resp.json()["id"]

    resp = await client.put(
        f"/catalysts/{catalyst_id}",
        json={"is_active": False},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_catalysts_ordered_by_created_desc(client):
    await _create_company(client)
    await _create_catalyst(client, description="First")
    await _create_catalyst(client, description="Second")
    await _create_catalyst(client, description="Third")

    resp = await client.get("/companies/SBER/catalysts")
    descriptions = [c["description"] for c in resp.json()]
    assert descriptions == ["Third", "Second", "First"]
