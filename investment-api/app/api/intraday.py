"""
API endpoints for intraday candles.

Author: AlmazNurmukhametov
"""

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_company, get_db
from app.models.intraday_candle import IntradayCandle
from app.schemas.intraday_candle import IntradayCandleResponse

router = APIRouter(tags=["intraday"])


@router.get("/companies/{ticker}/candles/intraday", response_model=list[IntradayCandleResponse])
async def list_intraday_candles(
    ticker: str,
    from_dt: Optional[dt.datetime] = Query(None, alias="from"),
    to_dt: Optional[dt.datetime] = Query(None, alias="to"),
    interval: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List intraday candles for a company."""
    company = await get_company(ticker, db)
    stmt = select(IntradayCandle).where(IntradayCandle.company_id == company.id)

    if from_dt:
        stmt = stmt.where(IntradayCandle.timestamp >= from_dt)
    if to_dt:
        stmt = stmt.where(IntradayCandle.timestamp <= to_dt)
    if interval:
        stmt = stmt.where(IntradayCandle.interval == interval)

    stmt = stmt.order_by(IntradayCandle.timestamp.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/companies/{ticker}/candles/intraday/latest", response_model=IntradayCandleResponse | None)
async def get_latest_intraday_candle(
    ticker: str,
    interval: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get latest intraday candle for a company."""
    company = await get_company(ticker, db)
    stmt = (
        select(IntradayCandle)
        .where(IntradayCandle.company_id == company.id)
    )
    if interval:
        stmt = stmt.where(IntradayCandle.interval == interval)

    stmt = stmt.order_by(IntradayCandle.timestamp.desc()).limit(1)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
