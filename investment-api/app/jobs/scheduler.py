"""
APScheduler integration for automated data fetching jobs.

Schedules:
- fetch_moex: daily at 19:00 MSK (16:00 UTC) — market snapshot
- fetch_prices: daily at 19:05 MSK (16:05 UTC) — OHLCV prices
- fetch_smartlab: daily at 09:00 MSK (06:00 UTC) — financial reports
- fetch_events: weekly on Sunday at 10:00 MSK (07:00 UTC) — dividends
- fetch_ir_calendar: weekly on Sunday at 10:30 MSK (07:30 UTC) — IR calendar events
- fetch_snapshots: hourly 10:00–19:00 MSK (07:00–16:00 UTC), weekdays — intraday price snapshots
- fetch_tinkoff_instruments: weekly on Sunday at 08:00 MSK (05:00 UTC) — FIGI mapping
- fetch_tinkoff_prices: daily at 19:10 MSK (16:10 UTC), weekdays — daily prices (backup)
- fetch_tinkoff_orderbook: every 30 min 10:00–18:30 MSK (07:00–15:30 UTC), weekdays — order book
- fetch_tinkoff_candles: every 15 min 10:00–19:00 MSK (07:00–16:00 UTC), weekdays — 15-min candles

Author: AlmazNurmukhametov
"""

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.db import async_session
from app.jobs.fetch_events import run_fetch_events
from app.jobs.fetch_ir_calendar import run_fetch_ir_calendar
from app.jobs.fetch_moex import run_fetch_moex
from app.jobs.fetch_snapshots import run_fetch_snapshots
from app.jobs.fetch_prices import run_fetch_prices
from app.jobs.fetch_smartlab import run_fetch_smartlab
from app.jobs.fetch_tinkoff import (
    run_fetch_tinkoff_candles,
    run_fetch_tinkoff_instruments,
    run_fetch_tinkoff_orderbook,
    run_fetch_tinkoff_prices,
)
from app.models import Company
from app.models.enums import JobStatusEnum
from app.models.job_run import JobRun

logger = logging.getLogger(__name__)


async def _run_job(job_name: str, fn: Callable[..., Awaitable[Any]]) -> None:
    """Wrapper that records job execution in job_runs table."""
    run = JobRun(job_name=job_name, status=JobStatusEnum.running)
    async with async_session() as db:
        db.add(run)
        await db.commit()
        await db.refresh(run)
        run_id = run.id

    start = time.monotonic()
    try:
        result = await fn()
        elapsed = round(time.monotonic() - start, 2)
        async with async_session() as db:
            run = await db.get(JobRun, run_id)
            run.status = JobStatusEnum.completed
            run.completed_at = datetime.now(UTC).replace(tzinfo=None)
            run.duration_seconds = elapsed
            run.result = json.dumps(result, default=str) if result else None
            await db.commit()
        logger.info("Job %s completed in %.1fs — %s", job_name, elapsed, result)
    except Exception as e:
        elapsed = round(time.monotonic() - start, 2)
        async with async_session() as db:
            run = await db.get(JobRun, run_id)
            run.status = JobStatusEnum.failed
            run.completed_at = datetime.now(UTC).replace(tzinfo=None)
            run.duration_seconds = elapsed
            run.error = str(e)
            await db.commit()
        logger.error("Job %s failed after %.1fs: %s", job_name, elapsed, e)


async def _do_fetch_moex() -> dict:
    async with async_session() as db:
        return await run_fetch_moex(db)


async def _do_fetch_prices() -> dict:
    async with async_session() as db:
        return await run_fetch_prices(db)


async def _do_fetch_smartlab() -> dict:
    async with async_session() as db:
        companies_result = await db.execute(select(Company.ticker))
        tickers = [row[0] for row in companies_result.all()]

    updated = 0
    errors = 0
    for ticker in tickers:
        try:
            async with async_session() as db:
                result = await run_fetch_smartlab(db, ticker)
                yearly = result.get("yearly", 0)
                quarterly = result.get("quarterly", 0)
                if yearly or quarterly:
                    updated += 1
                if result.get("errors"):
                    errors += 1
        except Exception as e:
            errors += 1
            logger.error("fetch_smartlab %s failed: %s", ticker, e)
        await asyncio.sleep(1)
    return {"tickers": len(tickers), "updated": updated, "errors": errors}


async def _do_fetch_events() -> dict:
    async with async_session() as db:
        companies_result = await db.execute(select(Company.ticker))
        tickers = [row[0] for row in companies_result.all()]

    errors = 0
    for ticker in tickers:
        try:
            async with async_session() as db:
                result = await run_fetch_events(db, ticker)
                if result.get("errors"):
                    errors += 1
        except Exception as e:
            errors += 1
            logger.error("fetch_events %s failed: %s", ticker, e)
    return {"tickers": len(tickers), "errors": errors}


async def _job_fetch_moex() -> None:
    await _run_job("fetch_moex", _do_fetch_moex)


async def _job_fetch_prices() -> None:
    await _run_job("fetch_prices", _do_fetch_prices)


async def _job_fetch_smartlab() -> None:
    await _run_job("fetch_smartlab", _do_fetch_smartlab)


async def _do_fetch_ir_calendar() -> dict:
    async with async_session() as db:
        return await run_fetch_ir_calendar(db)


async def _job_fetch_events() -> None:
    await _run_job("fetch_events", _do_fetch_events)


async def _job_fetch_ir_calendar() -> None:
    await _run_job("fetch_ir_calendar", _do_fetch_ir_calendar)


async def _do_fetch_snapshots() -> dict:
    async with async_session() as db:
        return await run_fetch_snapshots(db)


async def _job_fetch_snapshots() -> None:
    await _run_job("fetch_snapshots", _do_fetch_snapshots)


async def _do_fetch_tinkoff_instruments() -> dict:
    async with async_session() as db:
        return await run_fetch_tinkoff_instruments(db)


async def _job_fetch_tinkoff_instruments() -> None:
    await _run_job("fetch_tinkoff_instruments", _do_fetch_tinkoff_instruments)


async def _do_fetch_tinkoff_prices() -> dict:
    async with async_session() as db:
        return await run_fetch_tinkoff_prices(db)


async def _job_fetch_tinkoff_prices() -> None:
    await _run_job("fetch_tinkoff_prices", _do_fetch_tinkoff_prices)


async def _do_fetch_tinkoff_orderbook() -> dict:
    async with async_session() as db:
        return await run_fetch_tinkoff_orderbook(db)


async def _job_fetch_tinkoff_orderbook() -> None:
    await _run_job("fetch_tinkoff_orderbook", _do_fetch_tinkoff_orderbook)


async def _do_fetch_tinkoff_candles() -> dict:
    async with async_session() as db:
        return await run_fetch_tinkoff_candles(db)


async def _job_fetch_tinkoff_candles() -> None:
    await _run_job("fetch_tinkoff_candles", _do_fetch_tinkoff_candles)


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance.

    All times are UTC. Moscow is UTC+3, so:
    - 19:00 MSK = 16:00 UTC
    - 19:05 MSK = 16:05 UTC
    - 09:00 MSK = 06:00 UTC
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

    # Financial reports — daily at 09:00 MSK (06:00 UTC)
    scheduler.add_job(
        _job_fetch_smartlab,
        CronTrigger(hour=6, minute=0),
        id="fetch_smartlab",
        name="Fetch SmartLab financial reports",
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

    # IR calendar — weekly on Sunday at 10:30 MSK (07:30 UTC)
    scheduler.add_job(
        _job_fetch_ir_calendar,
        CronTrigger(hour=7, minute=30, day_of_week="sun"),
        id="fetch_ir_calendar",
        name="Fetch MOEX IR calendar",
        replace_existing=True,
    )

    # Intraday price snapshots — hourly 10:00–19:00 MSK (07:00–16:00 UTC), weekdays
    scheduler.add_job(
        _job_fetch_snapshots,
        CronTrigger(hour="7-16", minute=0, day_of_week="mon-fri"),
        id="fetch_snapshots",
        name="Fetch intraday price snapshots",
        replace_existing=True,
    )

    # Tinkoff: instrument mapping — weekly on Sunday at 08:00 MSK (05:00 UTC)
    scheduler.add_job(
        _job_fetch_tinkoff_instruments,
        CronTrigger(hour=5, minute=0, day_of_week="sun"),
        id="fetch_tinkoff_instruments",
        name="Fetch Tinkoff instrument mapping",
        replace_existing=True,
    )

    # Tinkoff: daily prices (backup) — weekdays at 19:10 MSK (16:10 UTC)
    scheduler.add_job(
        _job_fetch_tinkoff_prices,
        CronTrigger(hour=16, minute=10, day_of_week="mon-fri"),
        id="fetch_tinkoff_prices",
        name="Fetch Tinkoff daily prices",
        replace_existing=True,
    )

    # Tinkoff: order book — every 30 min, 10:00–18:30 MSK (07:00–15:30 UTC), weekdays
    scheduler.add_job(
        _job_fetch_tinkoff_orderbook,
        CronTrigger(hour="7-15", minute="0,30", day_of_week="mon-fri"),
        id="fetch_tinkoff_orderbook",
        name="Fetch Tinkoff order book",
        replace_existing=True,
    )

    # Tinkoff: intraday candles — every 15 min, 10:00–19:00 MSK (07:00–16:00 UTC), weekdays
    scheduler.add_job(
        _job_fetch_tinkoff_candles,
        CronTrigger(hour="7-16", minute="0,15,30,45", day_of_week="mon-fri"),
        id="fetch_tinkoff_candles",
        name="Fetch Tinkoff intraday candles",
        replace_existing=True,
    )

    return scheduler
