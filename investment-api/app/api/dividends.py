import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_company, get_db, require_api_key
from app.models import Dividend
from app.schemas import DividendCreate, DividendResponse

router = APIRouter(tags=["dividends"])


@router.get("/companies/{ticker}/dividends", response_model=list[DividendResponse])
async def list_dividends(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    company = await get_company(ticker, db)
    stmt = (
        select(Dividend)
        .where(Dividend.company_id == company.id)
        .order_by(Dividend.record_date.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/companies/{ticker}/dividends",
    response_model=DividendResponse,
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
async def create_dividend(
    ticker: str,
    data: DividendCreate,
    db: AsyncSession = Depends(get_db),
):
    company = await get_company(ticker, db)

    # Upsert by (company_id, record_date)
    stmt = select(Dividend).where(
        Dividend.company_id == company.id,
        Dividend.record_date == data.record_date,
    )
    result = await db.execute(stmt)
    dividend = result.scalar_one_or_none()

    if dividend:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(dividend, field, value)
    else:
        dividend = Dividend(company_id=company.id, **data.model_dump())
        db.add(dividend)

    await db.commit()
    await db.refresh(dividend)
    return dividend


@router.get("/dividends/upcoming", response_model=list[DividendResponse])
async def upcoming_dividends(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    today = dt.date.today()
    stmt = (
        select(Dividend)
        .where(Dividend.record_date >= today)
        .order_by(Dividend.record_date.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
