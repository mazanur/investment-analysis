"""
API endpoints for triggering server-side data jobs.

All job endpoints require API key auth (write operations).
Job runs are recorded in the job_runs table for monitoring.

Author: AlmazNurmukhametov
"""

import json
import time
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_api_key
from app.jobs.fetch_events import run_fetch_events
from app.jobs.fetch_ir_calendar import run_fetch_ir_calendar
from app.jobs.fetch_moex import run_fetch_moex
from app.jobs.fetch_snapshots import run_fetch_snapshots
from app.jobs.fetch_prices import run_fetch_prices
from app.jobs.fetch_smartlab import run_fetch_smartlab
from app.models.enums import JobStatusEnum
from app.models.job_run import JobRun

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(require_api_key)])


async def _record_job(db: AsyncSession, job_name: str, fn, **kwargs) -> dict:
    """Execute job and record run in job_runs table."""
    run = JobRun(job_name=job_name, status=JobStatusEnum.running)
    db.add(run)
    await db.commit()
    await db.refresh(run)

    start = time.monotonic()
    try:
        result = await fn(db, **kwargs)
        elapsed = round(time.monotonic() - start, 2)
        run.status = JobStatusEnum.completed
        run.completed_at = datetime.now(UTC).replace(tzinfo=None)
        run.duration_seconds = elapsed
        run.result = json.dumps(result, default=str) if result else None
        await db.commit()
        return result
    except Exception as e:
        elapsed = round(time.monotonic() - start, 2)
        run.status = JobStatusEnum.failed
        run.completed_at = datetime.now(UTC).replace(tzinfo=None)
        run.duration_seconds = elapsed
        run.error = str(e)
        await db.commit()
        raise


@router.post("/fetch-moex")
async def trigger_fetch_moex(
    tickers: Optional[list[str]] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Fetch market snapshot from MOEX ISS and update companies table."""
    return await _record_job(db, "fetch_moex", run_fetch_moex, tickers=tickers)


@router.post("/fetch-prices")
async def trigger_fetch_prices(
    tickers: Optional[list[str]] = Query(None),
    backfill_days: int = Query(0, ge=0, le=3650),
    db: AsyncSession = Depends(get_db),
):
    """Fetch OHLCV prices from MOEX ISS and upsert into prices table."""
    return await _record_job(db, "fetch_prices", run_fetch_prices, tickers=tickers, backfill_days=backfill_days)


@router.post("/fetch-smartlab/{ticker}")
async def trigger_fetch_smartlab(
    ticker: str,
    period_types: Optional[list[str]] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Fetch financial reports from smart-lab.ru for a specific ticker."""
    return await _record_job(db, f"fetch_smartlab:{ticker.upper()}", run_fetch_smartlab, ticker=ticker.upper(), period_types=period_types)


@router.post("/fetch-events/{ticker}")
async def trigger_fetch_events(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch dividends from MOEX ISS for a specific ticker."""
    return await _record_job(db, f"fetch_events:{ticker.upper()}", run_fetch_events, ticker=ticker.upper())


@router.post("/fetch-ir-calendar")
async def trigger_fetch_ir_calendar(
    db: AsyncSession = Depends(get_db),
):
    """Fetch IR calendar events from MOEX ISS and upsert as catalysts."""
    return await _record_job(db, "fetch_ir_calendar", run_fetch_ir_calendar)


@router.post("/fetch-snapshots")
async def trigger_fetch_snapshots(
    db: AsyncSession = Depends(get_db),
):
    """Fetch intraday price snapshots from MOEX ISS for all companies."""
    return await _record_job(db, "fetch_snapshots", run_fetch_snapshots)
