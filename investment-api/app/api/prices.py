import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
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
    db: AsyncSession = Depends(get_db),
):
    company = await get_company(ticker, db)
    stmt = select(Price).where(Price.company_id == company.id)

    if from_date:
        stmt = stmt.where(Price.date >= from_date)
    if to_date:
        stmt = stmt.where(Price.date <= to_date)

    stmt = stmt.order_by(Price.date.desc())
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
    results = []

    for price_data in data.prices:
        # Upsert by (company_id, date)
        stmt = select(Price).where(
            Price.company_id == company.id,
            Price.date == price_data.date,
        )
        result = await db.execute(stmt)
        price = result.scalar_one_or_none()

        if price:
            for field, value in price_data.model_dump(exclude_unset=True).items():
                setattr(price, field, value)
        else:
            price = Price(company_id=company.id, **price_data.model_dump())
            db.add(price)

        results.append(price)

    await db.commit()
    for p in results:
        await db.refresh(p)
    return results
