"""Tests for scheduler configuration and health endpoint."""

import pytest

from app.jobs.scheduler import create_scheduler


def test_create_scheduler_has_three_jobs():
    """Scheduler should have 3 configured jobs."""
    scheduler = create_scheduler()
    jobs = scheduler.get_jobs()
    assert len(jobs) == 3

    job_ids = {j.id for j in jobs}
    assert job_ids == {"fetch_moex", "fetch_prices", "fetch_events"}


def test_fetch_moex_schedule():
    """fetch_moex should run at 16:00 UTC weekdays."""
    scheduler = create_scheduler()
    job = scheduler.get_job("fetch_moex")
    trigger = job.trigger

    assert str(trigger) == "cron[day_of_week='mon-fri', hour='16', minute='0']"


def test_fetch_prices_schedule():
    """fetch_prices should run at 16:05 UTC weekdays."""
    scheduler = create_scheduler()
    job = scheduler.get_job("fetch_prices")
    trigger = job.trigger

    assert str(trigger) == "cron[day_of_week='mon-fri', hour='16', minute='5']"


def test_fetch_events_schedule():
    """fetch_events should run at 07:00 UTC on Sundays."""
    scheduler = create_scheduler()
    job = scheduler.get_job("fetch_events")
    trigger = job.trigger

    assert str(trigger) == "cron[day_of_week='sun', hour='7', minute='0']"


def test_scheduler_timezone_is_utc():
    """Scheduler should use UTC timezone."""
    scheduler = create_scheduler()
    assert str(scheduler.timezone) == "UTC"


@pytest.mark.asyncio
async def test_health_endpoint_returns_db_status(client):
    """Health endpoint should check DB connectivity."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_health_endpoint_structure(client):
    """Health response should have status and database fields."""
    response = await client.get("/health")
    data = response.json()
    assert "status" in data
    assert "database" in data
