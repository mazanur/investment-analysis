"""
API endpoints for intraday price snapshots.

Author: AlmazNurmukhametov
"""

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_company, get_db
from app.models.price_snapshot import PriceSnapshot
from app.schemas.price_snapshot import PriceSnapshotResponse

router = APIRouter(tags=["snapshots"])


@router.get("/companies/{ticker}/snapshots", response_model=list[PriceSnapshotResponse])
async def list_snapshots(
    ticker: str,
    from_dt: Optional[dt.datetime] = Query(None, alias="from"),
    to_dt: Optional[dt.datetime] = Query(None, alias="to"),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List intraday price snapshots for a company."""
    company = await get_company(ticker, db)
    stmt = select(PriceSnapshot).where(PriceSnapshot.company_id == company.id)

    if from_dt:
        stmt = stmt.where(PriceSnapshot.timestamp >= from_dt)
    if to_dt:
        stmt = stmt.where(PriceSnapshot.timestamp <= to_dt)

    stmt = stmt.order_by(PriceSnapshot.timestamp.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()
