"""
APScheduler integration for automated data fetching jobs.

Schedules:
- fetch_moex: daily at 19:00 MSK (16:00 UTC) — market snapshot
- fetch_prices: daily at 19:05 MSK (16:05 UTC) — OHLCV prices
- fetch_events: weekly on Sunday at 10:00 MSK (07:00 UTC) — dividends

Author: AlmazNurmukhametov
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db import async_session
from app.jobs.fetch_events import run_fetch_events
from app.jobs.fetch_moex import run_fetch_moex
from app.jobs.fetch_prices import run_fetch_prices

logger = logging.getLogger(__name__)


async def _job_fetch_moex() -> None:
    """Scheduled job: fetch market snapshot from MOEX."""
    logger.info("Scheduler: starting fetch_moex job")
    async with async_session() as db:
        result = await run_fetch_moex(db)
    logger.info("Scheduler: fetch_moex done — %s", result)


async def _job_fetch_prices() -> None:
    """Scheduled job: fetch daily prices from MOEX."""
    logger.info("Scheduler: starting fetch_prices job")
    async with async_session() as db:
        result = await run_fetch_prices(db)
    logger.info("Scheduler: fetch_prices done — %s", result)


async def _job_fetch_events() -> None:
    """Scheduled job: fetch dividends for all companies."""
    logger.info("Scheduler: starting fetch_events job")
    async with async_session() as db:
        from sqlalchemy import select

        from app.models import Company

        companies_result = await db.execute(select(Company.ticker))
        tickers = [row[0] for row in companies_result.all()]

    for ticker in tickers:
        async with async_session() as db:
            result = await run_fetch_events(db, ticker)
            if result.get("errors"):
                logger.warning("Scheduler: fetch_events %s errors: %s", ticker, result["errors"])
    logger.info("Scheduler: fetch_events done for %d tickers", len(tickers))


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance.

    All times are UTC. Moscow is UTC+3, so:
    - 19:00 MSK = 16:00 UTC
    - 19:05 MSK = 16:05 UTC
    - 10:00 MSK = 07:00 UTC
    """
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Market snapshot — daily at 19:00 MSK (16:00 UTC), weekdays only
    scheduler.add_job(
        _job_fetch_moex,
        CronTrigger(hour=16, minute=0, day_of_week="mon-fri"),
        id="fetch_moex",
        name="Fetch MOEX market snapshot",
        replace_existing=True,
    )

    # Daily prices — daily at 19:05 MSK (16:05 UTC), weekdays only
    scheduler.add_job(
        _job_fetch_prices,
        CronTrigger(hour=16, minute=5, day_of_week="mon-fri"),
        id="fetch_prices",
        name="Fetch MOEX daily prices",
        replace_existing=True,
    )

    # Dividends/events — weekly on Sunday at 10:00 MSK (07:00 UTC)
    scheduler.add_job(
        _job_fetch_events,
        CronTrigger(hour=7, minute=0, day_of_week="sun"),
        id="fetch_events",
        name="Fetch MOEX dividends/events",
        replace_existing=True,
    )

    return scheduler
