import pytest

API_KEY = "dev-api-key"
HEADERS = {"X-API-Key": API_KEY}


async def _create_company(client, ticker="SBER", name="Sberbank"):
    resp = await client.post(f"/companies/{ticker}", json={"ticker": ticker, "name": name}, headers=HEADERS)
    return resp.json()


async def _create_news(client, **kwargs):
    data = {"date": "2026-03-01", "title": "Test news", **kwargs}
    resp = await client.post("/news", json=data, headers=HEADERS)
    return resp.json()


async def _create_signal(client, ticker="SBER", **kwargs):
    data = {
        "date": "2026-03-01",
        "signal": "buy",
        "direction": "long-positive",
        "confidence": 75,
        "entry_price": 310.5,
        "take_profit": 350.0,
        "stop_loss": 295.0,
        "risk_reward": 2.5,
        "position_size": "half",
        "reasoning": "Strong Q4 earnings expected",
        **kwargs,
    }
    return await client.post(f"/companies/{ticker}/signals", json=data, headers=HEADERS)


@pytest.mark.asyncio
async def test_create_signal(client):
    await _create_company(client)
    resp = await _create_signal(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["signal"] == "buy"
    assert body["direction"] == "long-positive"
    assert float(body["confidence"]) == 75.0
    assert float(body["entry_price"]) == 310.5
    assert float(body["take_profit"]) == 350.0
    assert float(body["stop_loss"]) == 295.0
    assert float(body["risk_reward"]) == 2.5
    assert body["position_size"] == "half"
    assert body["reasoning"] == "Strong Q4 earnings expected"
    assert body["status"] == "active"
    assert body["company_id"] is not None
    assert "id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_create_signal_with_news_link(client):
    company = await _create_company(client)
    news = await _create_news(client, company_id=company["id"], title="Earnings report")
    resp = await _create_signal(client, news_id=news["id"])
    assert resp.status_code == 201
    assert resp.json()["news_id"] == news["id"]


@pytest.mark.asyncio
async def test_create_signal_requires_api_key(client):
    await _create_company(client)
    resp = await client.post(
        "/companies/SBER/signals",
        json={"date": "2026-03-01", "signal": "buy", "direction": "long-positive", "confidence": 50},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_signal_invalid_api_key(client):
    await _create_company(client)
    resp = await client.post(
        "/companies/SBER/signals",
        json={"date": "2026-03-01", "signal": "buy", "direction": "long-positive", "confidence": 50},
        headers={"X-API-Key": "wrong"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_signal_company_not_found(client):
    resp = await _create_signal(client, ticker="NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_signals(client):
    await _create_company(client)
    await _create_signal(client, reasoning="Signal 1")
    await _create_signal(client, reasoning="Signal 2")

    resp = await client.get("/companies/SBER/signals")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Ordered by created_at desc
    assert data[0]["reasoning"] == "Signal 2"
    assert data[1]["reasoning"] == "Signal 1"


@pytest.mark.asyncio
async def test_list_signals_company_not_found(client):
    resp = await client.get("/companies/NONEXISTENT/signals")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_filter_signals_by_status(client):
    await _create_company(client)
    resp1 = await _create_signal(client, reasoning="Active one")
    await _create_signal(client, reasoning="Also active")

    # Close the first one
    signal_id = resp1.json()["id"]
    await client.put(
        f"/signals/{signal_id}",
        json={"status": "closed", "result_pct": 12.5},
        headers=HEADERS,
    )

    # Filter active only
    resp = await client.get("/companies/SBER/signals?status=active")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["reasoning"] == "Also active"

    # Filter closed only
    resp = await client.get("/companies/SBER/signals?status=closed")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["reasoning"] == "Active one"


@pytest.mark.asyncio
async def test_close_signal_with_result(client):
    await _create_company(client)
    create_resp = await _create_signal(client)
    signal_id = create_resp.json()["id"]

    resp = await client.put(
        f"/signals/{signal_id}",
        json={"status": "closed", "result_pct": 15.3},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "closed"
    assert float(body["result_pct"]) == 15.3
    assert body["closed_at"] is not None


@pytest.mark.asyncio
async def test_close_signal_with_explicit_closed_at(client):
    await _create_company(client)
    create_resp = await _create_signal(client)
    signal_id = create_resp.json()["id"]

    resp = await client.put(
        f"/signals/{signal_id}",
        json={"status": "closed", "result_pct": -5.0, "closed_at": "2026-03-05T14:00:00"},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "closed"
    assert "2026-03-05" in body["closed_at"]


@pytest.mark.asyncio
async def test_expire_signal(client):
    await _create_company(client)
    create_resp = await _create_signal(client)
    signal_id = create_resp.json()["id"]

    resp = await client.put(
        f"/signals/{signal_id}",
        json={"status": "expired"},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "expired"
    assert body["closed_at"] is not None


@pytest.mark.asyncio
async def test_update_signal_not_found(client):
    resp = await client.put(
        "/signals/99999",
        json={"status": "closed"},
        headers=HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_signal_requires_api_key(client):
    await _create_company(client)
    create_resp = await _create_signal(client)
    signal_id = create_resp.json()["id"]

    resp = await client.put(f"/signals/{signal_id}", json={"status": "closed"})
    assert resp.status_code == 422
