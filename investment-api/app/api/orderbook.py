"""
API endpoints for order book snapshots.

Author: AlmazNurmukhametov
"""

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_company, get_db
from app.models.order_book_snapshot import OrderBookSnapshot
from app.schemas.order_book_snapshot import OrderBookSnapshotResponse

router = APIRouter(tags=["orderbook"])


@router.get("/companies/{ticker}/orderbook", response_model=list[OrderBookSnapshotResponse])
async def list_orderbook_snapshots(
    ticker: str,
    from_dt: Optional[dt.datetime] = Query(None, alias="from"),
    to_dt: Optional[dt.datetime] = Query(None, alias="to"),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List order book snapshots for a company."""
    company = await get_company(ticker, db)
    stmt = select(OrderBookSnapshot).where(OrderBookSnapshot.company_id == company.id)

    if from_dt:
        stmt = stmt.where(OrderBookSnapshot.timestamp >= from_dt)
    if to_dt:
        stmt = stmt.where(OrderBookSnapshot.timestamp <= to_dt)

    stmt = stmt.order_by(OrderBookSnapshot.timestamp.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/companies/{ticker}/orderbook/latest", response_model=OrderBookSnapshotResponse | None)
async def get_latest_orderbook(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """Get latest order book snapshot for a company."""
    company = await get_company(ticker, db)
    stmt = (
        select(OrderBookSnapshot)
        .where(OrderBookSnapshot.company_id == company.id)
        .order_by(OrderBookSnapshot.timestamp.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
