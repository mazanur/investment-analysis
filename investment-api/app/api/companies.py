from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, require_api_key
from app.models import Catalyst, Company, Dividend, Price, Sector
from app.models.enums import PositionEnum, SentimentEnum
from app.schemas import CompanyCreate, CompanyListResponse, CompanyResponse, CompanyUpdate

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyListResponse])
async def list_companies(
    sector: Optional[str] = Query(None),
    sentiment: Optional[SentimentEnum] = Query(None),
    position: Optional[PositionEnum] = Query(None),
    min_upside: Optional[Decimal] = Query(None),
    max_p_e: Optional[Decimal] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Company)

    if sector:
        stmt = stmt.join(Sector).where(Sector.slug == sector)
    if sentiment:
        stmt = stmt.where(Company.sentiment == sentiment)
    if position:
        stmt = stmt.where(Company.position == position)
    if min_upside is not None:
        stmt = stmt.where(Company.upside >= min_upside)
    if max_p_e is not None:
        stmt = stmt.where(Company.p_e <= max_p_e)

    stmt = stmt.order_by(Company.ticker)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{ticker}", response_model=CompanyResponse)
async def get_company(ticker: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).where(Company.ticker == ticker))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Latest price
    price_result = await db.execute(
        select(Price).where(Price.company_id == company.id).order_by(Price.date.desc()).limit(1)
    )
    latest_price = price_result.scalar_one_or_none()

    # Active catalysts
    catalysts_result = await db.execute(
        select(Catalyst)
        .where(Catalyst.company_id == company.id, Catalyst.is_active.is_(True))
        .order_by(Catalyst.created_at.desc())
    )
    active_catalysts = catalysts_result.scalars().all()

    # Last dividend
    dividend_result = await db.execute(
        select(Dividend).where(Dividend.company_id == company.id).order_by(Dividend.record_date.desc()).limit(1)
    )
    last_dividend = dividend_result.scalar_one_or_none()

    response = CompanyResponse.model_validate(company)
    response.latest_price = latest_price
    response.active_catalysts = active_catalysts
    response.last_dividend = last_dividend
    return response


@router.post("/{ticker}", response_model=CompanyResponse, status_code=201, dependencies=[Depends(require_api_key)])
async def upsert_company(ticker: str, data: CompanyCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).where(Company.ticker == ticker))
    company = result.scalar_one_or_none()

    if company:
        for field, value in data.model_dump(exclude={"ticker"}, exclude_unset=True).items():
            setattr(company, field, value)
        await db.commit()
        await db.refresh(company)
    else:
        company = Company(ticker=ticker, **data.model_dump(exclude={"ticker"}))
        db.add(company)
        await db.commit()
        await db.refresh(company)

    return CompanyResponse.model_validate(company)


@router.put("/{ticker}", response_model=CompanyResponse, dependencies=[Depends(require_api_key)])
async def update_company(ticker: str, data: CompanyUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).where(Company.ticker == ticker))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    await db.commit()
    await db.refresh(company)
    return CompanyResponse.model_validate(company)
