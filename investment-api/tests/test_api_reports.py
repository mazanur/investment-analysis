import pytest

API_KEY = "dev-api-key"
HEADERS = {"X-API-Key": API_KEY}


async def _create_company(client, ticker="SBER", name="Sberbank"):
    resp = await client.post(f"/companies/{ticker}", json={"ticker": ticker, "name": name}, headers=HEADERS)
    return resp.json()


async def _create_report(client, ticker="SBER", period="2024Q4", period_type="quarterly", **kwargs):
    data = {"period": period, "period_type": period_type, **kwargs}
    return await client.post(f"/companies/{ticker}/reports", json=data, headers=HEADERS)


@pytest.mark.asyncio
async def test_list_reports_empty(client):
    await _create_company(client)
    resp = await client.get("/companies/SBER/reports")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_reports_company_not_found(client):
    resp = await client.get("/companies/NONEXISTENT/reports")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_report(client):
    await _create_company(client)
    resp = await _create_report(
        client,
        period="2024Q4",
        period_type="quarterly",
        revenue="1500000.00",
        net_income="300000.00",
        roe="25.00",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["period"] == "2024Q4"
    assert body["period_type"] == "quarterly"
    assert body["revenue"] == "1500000.00"
    assert body["net_income"] == "300000.00"
    assert "id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_create_report_requires_api_key(client):
    await _create_company(client)
    resp = await client.post(
        "/companies/SBER/reports",
        json={"period": "2024Q4", "period_type": "quarterly"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_report_invalid_api_key(client):
    await _create_company(client)
    resp = await client.post(
        "/companies/SBER/reports",
        json={"period": "2024Q4", "period_type": "quarterly"},
        headers={"X-API-Key": "wrong"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_report_company_not_found(client):
    resp = await _create_report(client, ticker="NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upsert_report_updates_existing(client):
    await _create_company(client)
    resp1 = await _create_report(client, period="2024Q4", revenue="1000000.00")
    assert resp1.status_code == 201
    id1 = resp1.json()["id"]

    # Same period -> upsert (update)
    resp2 = await _create_report(client, period="2024Q4", revenue="1500000.00")
    assert resp2.status_code == 201
    assert resp2.json()["id"] == id1
    assert resp2.json()["revenue"] == "1500000.00"


@pytest.mark.asyncio
async def test_filter_by_period_type(client):
    await _create_company(client)
    await _create_report(client, period="2024Q4", period_type="quarterly")
    await _create_report(client, period="2024", period_type="yearly")

    resp = await client.get("/companies/SBER/reports?period_type=quarterly")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["period"] == "2024Q4"

    resp = await client.get("/companies/SBER/reports?period_type=yearly")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["period"] == "2024"


@pytest.mark.asyncio
async def test_list_reports_ordered_by_period_desc(client):
    await _create_company(client)
    await _create_report(client, period="2024Q1")
    await _create_report(client, period="2024Q4")
    await _create_report(client, period="2024Q2")

    resp = await client.get("/companies/SBER/reports")
    periods = [r["period"] for r in resp.json()]
    assert periods == ["2024Q4", "2024Q2", "2024Q1"]


@pytest.mark.asyncio
async def test_get_latest_report(client):
    await _create_company(client)
    await _create_report(client, period="2024Q1", revenue="100000.00")
    await _create_report(client, period="2024Q4", revenue="400000.00")
    await _create_report(client, period="2024Q2", revenue="200000.00")

    resp = await client.get("/companies/SBER/reports/latest")
    assert resp.status_code == 200
    assert resp.json()["period"] == "2024Q4"
    assert resp.json()["revenue"] == "400000.00"


@pytest.mark.asyncio
async def test_get_latest_report_with_period_type_filter(client):
    await _create_company(client)
    await _create_report(client, period="2024", period_type="yearly", revenue="1000000.00")
    await _create_report(client, period="2024Q4", period_type="quarterly", revenue="400000.00")

    resp = await client.get("/companies/SBER/reports/latest?period_type=quarterly")
    assert resp.status_code == 200
    assert resp.json()["period"] == "2024Q4"

    resp = await client.get("/companies/SBER/reports/latest?period_type=yearly")
    assert resp.status_code == 200
    assert resp.json()["period"] == "2024"


@pytest.mark.asyncio
async def test_get_latest_report_not_found(client):
    await _create_company(client)
    resp = await client.get("/companies/SBER/reports/latest")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_latest_report_company_not_found(client):
    resp = await client.get("/companies/NONEXISTENT/reports/latest")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_report_with_extra_metrics(client):
    await _create_company(client)
    resp = await _create_report(
        client,
        period="2024Q4",
        extra_metrics={"nim": 6.2, "npl_ratio": 2.1, "cost_income": 28.5},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["extra_metrics"]["nim"] == 6.2
    assert body["extra_metrics"]["npl_ratio"] == 2.1


@pytest.mark.asyncio
async def test_create_report_with_all_fields(client):
    await _create_company(client)
    resp = await _create_report(
        client,
        period="2024Q4",
        period_type="quarterly",
        report_date="2025-03-01",
        net_income="300000.00",
        revenue="1500000.00",
        equity="5000000.00",
        total_debt="2000000.00",
        net_debt="1500000.00",
        roe="25.00",
        eps="50.00",
        p_e="4.50",
        p_bv="1.20",
        dividend_yield="12.00",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["report_date"] == "2025-03-01"
    assert body["equity"] == "5000000.00"
    assert body["total_debt"] == "2000000.00"
    assert body["eps"] == "50.00"
