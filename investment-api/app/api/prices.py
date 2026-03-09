import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_company, get_db, require_api_key
from app.models import Price
from app.schemas import PriceBulkCreate, PriceResponse

router = APIRouter(tags=["prices"])


@router.get("/companies/{ticker}/prices", response_model=list[PriceResponse])
async def list_prices(
    ticker: str,
    from_date: Optional[dt.date] = Query(None, alias="from"),
    to_date: Optional[dt.date] = Query(None, alias="to"),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    company = await get_company(ticker, db)
    stmt = select(Price).where(Price.company_id == company.id)

    if from_date:
        stmt = stmt.where(Price.date >= from_date)
    if to_date:
        stmt = stmt.where(Price.date <= to_date)

    stmt = stmt.order_by(Price.date.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/companies/{ticker}/prices/latest", response_model=PriceResponse)
async def get_latest_price(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    company = await get_company(ticker, db)
    stmt = (
        select(Price)
        .where(Price.company_id == company.id)
        .order_by(Price.date.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    price = result.scalar_one_or_none()
    if not price:
        raise HTTPException(status_code=404, detail="No prices found")
    return price


@router.post(
    "/companies/{ticker}/prices",
    response_model=list[PriceResponse],
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
async def bulk_upsert_prices(
    ticker: str,
    data: PriceBulkCreate,
    db: AsyncSession = Depends(get_db),
):
    company = await get_company(ticker, db)

    # Deduplicate by date (last entry wins)
    deduped: dict[dt.date, object] = {}
    for p in data.prices:
        deduped[p.date] = p
    unique_prices = list(deduped.values())

    if not unique_prices:
        return []

    # Use PostgreSQL INSERT ON CONFLICT DO UPDATE (atomic upsert, no race conditions)
    # Use COALESCE to preserve existing non-NULL values when new values are NULL,
    # so clients that omit optional fields don't erase existing OHLCV/market_cap data.
    values = [{"company_id": company.id, **p.model_dump()} for p in unique_prices]
    stmt = pg_insert(Price).values(values)
    cols = Price.__table__.c
    stmt = stmt.on_conflict_do_update(
        constraint="uq_price_company_date",
        set_={
            "open": func.coalesce(stmt.excluded.open, cols.open),
            "high": func.coalesce(stmt.excluded.high, cols.high),
            "low": func.coalesce(stmt.excluded.low, cols.low),
            "close": stmt.excluded.close,
            "volume_rub": func.coalesce(stmt.excluded.volume_rub, cols.volume_rub),
            "market_cap": func.coalesce(stmt.excluded.market_cap, cols.market_cap),
        },
    )
    await db.execute(stmt)
    await db.commit()

    # Fetch the upserted rows
    dates = [p.date for p in unique_prices]
    result = await db.execute(
        select(Price).where(Price.company_id == company.id, Price.date.in_(dates))
    )
    return result.scalars().all()
