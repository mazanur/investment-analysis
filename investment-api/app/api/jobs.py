"""
API endpoints for triggering server-side data jobs.

All job endpoints require API key auth (write operations).

Author: AlmazNurmukhametov
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_api_key
from app.jobs.fetch_events import run_fetch_events
from app.jobs.fetch_moex import run_fetch_moex
from app.jobs.fetch_prices import run_fetch_prices
from app.jobs.fetch_smartlab import run_fetch_smartlab

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(require_api_key)])


@router.post("/fetch-moex")
async def trigger_fetch_moex(
    tickers: Optional[list[str]] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Fetch market snapshot from MOEX ISS and update companies table."""
    result = await run_fetch_moex(db, tickers=tickers)
    return result


@router.post("/fetch-prices")
async def trigger_fetch_prices(
    tickers: Optional[list[str]] = Query(None),
    backfill_days: int = Query(0, ge=0, le=3650),
    db: AsyncSession = Depends(get_db),
):
    """Fetch OHLCV prices from MOEX ISS and upsert into prices table."""
    result = await run_fetch_prices(db, tickers=tickers, backfill_days=backfill_days)
    return result


@router.post("/fetch-smartlab/{ticker}")
async def trigger_fetch_smartlab(
    ticker: str,
    period_types: Optional[list[str]] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Fetch financial reports from smart-lab.ru for a specific ticker."""
    result = await run_fetch_smartlab(db, ticker=ticker.upper(), period_types=period_types)
    return result


@router.post("/fetch-events/{ticker}")
async def trigger_fetch_events(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch dividends from MOEX ISS for a specific ticker."""
    result = await run_fetch_events(db, ticker=ticker.upper())
    return result
