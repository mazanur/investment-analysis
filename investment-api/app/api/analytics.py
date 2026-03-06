from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models import Company, Sector
from app.models.enums import PositionEnum, SentimentEnum
from app.schemas.analytics import OverdueItem, ScreenerItem, SectorSummaryItem, TopUpsideItem

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/top-upside", response_model=list[TopUpsideItem])
async def top_upside(
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Company, Sector.slug.label("sector_slug"))
        .outerjoin(Sector, Company.sector_id == Sector.id)
        .where(Company.upside.is_not(None))
        .order_by(Company.upside.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        TopUpsideItem(
            ticker=company.ticker,
            name=company.name,
            sector_slug=sector_slug,
            sentiment=company.sentiment,
            position=company.position,
            current_price=company.current_price,
            my_fair_value=company.my_fair_value,
            upside=company.upside,
        )
        for company, sector_slug in rows
    ]


@router.get("/screener", response_model=list[ScreenerItem])
async def screener(
    sector: Optional[str] = Query(None),
    sentiment: Optional[SentimentEnum] = Query(None),
    position: Optional[PositionEnum] = Query(None),
    min_upside: Optional[Decimal] = Query(None),
    max_p_e: Optional[Decimal] = Query(None),
    min_dividend_yield: Optional[Decimal] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Company, Sector.slug.label("sector_slug")).outerjoin(
        Sector, Company.sector_id == Sector.id
    )

    if sector:
        stmt = stmt.where(Sector.slug == sector)
    if sentiment:
        stmt = stmt.where(Company.sentiment == sentiment)
    if position:
        stmt = stmt.where(Company.position == position)
    if min_upside is not None:
        stmt = stmt.where(Company.upside >= min_upside)
    if max_p_e is not None:
        stmt = stmt.where(Company.p_e <= max_p_e)
    if min_dividend_yield is not None:
        stmt = stmt.where(Company.dividend_yield >= min_dividend_yield)

    stmt = stmt.order_by(Company.ticker)
    result = await db.execute(stmt)
    rows = result.all()
    return [
        ScreenerItem(
            ticker=company.ticker,
            name=company.name,
            sector_slug=sector_slug,
            sentiment=company.sentiment,
            position=company.position,
            current_price=company.current_price,
            upside=company.upside,
            p_e=company.p_e,
            dividend_yield=company.dividend_yield,
            roe=company.roe,
            market_cap=company.market_cap,
        )
        for company, sector_slug in rows
    ]


@router.get("/sector-summary", response_model=list[SectorSummaryItem])
async def sector_summary(
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(
            Sector.slug,
            Sector.name,
            func.count(Company.id).label("company_count"),
            func.sum(case((Company.sentiment == SentimentEnum.bullish, 1), else_=0)).label(
                "bullish_count"
            ),
            func.sum(case((Company.sentiment == SentimentEnum.neutral, 1), else_=0)).label(
                "neutral_count"
            ),
            func.sum(case((Company.sentiment == SentimentEnum.bearish, 1), else_=0)).label(
                "bearish_count"
            ),
            func.avg(Company.upside).label("avg_upside"),
        )
        .join(Company, Company.sector_id == Sector.id)
        .group_by(Sector.id, Sector.slug, Sector.name)
        .order_by(Sector.name)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        SectorSummaryItem(
            slug=row.slug,
            name=row.name,
            company_count=row.company_count,
            bullish_count=row.bullish_count,
            neutral_count=row.neutral_count,
            bearish_count=row.bearish_count,
            avg_upside=Decimal(str(round(row.avg_upside, 4))) if row.avg_upside is not None else None,
        )
        for row in rows
    ]


@router.get("/overdue", response_model=list[OverdueItem])
async def overdue(
    days: int = Query(90, ge=0, description="Threshold in days since last update"),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(UTC)
    stmt = (
        select(Company, Sector.slug.label("sector_slug"))
        .outerjoin(Sector, Company.sector_id == Sector.id)
        .order_by(Company.updated_at.asc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    overdue_items = []
    for company, sector_slug in rows:
        updated = company.updated_at
        if updated.tzinfo is None:
            delta = (now.replace(tzinfo=None) - updated).days
        else:
            delta = (now - updated).days
        if delta >= days:
            overdue_items.append(
                OverdueItem(
                    ticker=company.ticker,
                    name=company.name,
                    sector_slug=sector_slug,
                    updated_at=updated.isoformat(),
                    days_since_update=delta,
                )
            )
    return overdue_items
