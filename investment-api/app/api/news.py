import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_api_key
from app.models import Company, News, Sector
from app.schemas import NewsCreate, NewsResponse, NewsUpdate

router = APIRouter(tags=["news"])


async def _get_company(ticker: str, db: AsyncSession) -> Company:
    result = await db.execute(select(Company).where(Company.ticker == ticker))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


async def _get_sector(slug: str, db: AsyncSession) -> Sector:
    result = await db.execute(select(Sector).where(Sector.slug == slug))
    sector = result.scalar_one_or_none()
    if not sector:
        raise HTTPException(status_code=404, detail="Sector not found")
    return sector


@router.get("/companies/{ticker}/news", response_model=list[NewsResponse])
async def list_company_news(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    company = await _get_company(ticker, db)
    stmt = (
        select(News)
        .where(News.company_id == company.id)
        .order_by(News.date.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/sectors/{slug}/news", response_model=list[NewsResponse])
async def list_sector_news(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    sector = await _get_sector(slug, db)
    stmt = (
        select(News)
        .where(News.sector_id == sector.id)
        .order_by(News.date.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/news", response_model=list[NewsResponse])
async def list_news(
    impact: Optional[str] = Query(None),
    from_date: Optional[dt.date] = Query(None, alias="from"),
    to_date: Optional[dt.date] = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(News)

    if impact:
        stmt = stmt.where(News.impact == impact)
    if from_date:
        stmt = stmt.where(News.date >= from_date)
    if to_date:
        stmt = stmt.where(News.date <= to_date)

    stmt = stmt.order_by(News.date.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/news",
    response_model=NewsResponse,
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
async def create_news(
    data: NewsCreate,
    db: AsyncSession = Depends(get_db),
):
    # Validate company_id if provided
    if data.company_id is not None:
        result = await db.execute(select(Company).where(Company.id == data.company_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Company not found")

    # Validate sector_id if provided
    if data.sector_id is not None:
        result = await db.execute(select(Sector).where(Sector.id == data.sector_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Sector not found")

    news = News(**data.model_dump())
    db.add(news)
    await db.commit()
    await db.refresh(news)
    return news


@router.put(
    "/news/{news_id}",
    response_model=NewsResponse,
    dependencies=[Depends(require_api_key)],
)
async def update_news(
    news_id: int,
    data: NewsUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(News).where(News.id == news_id))
    news = result.scalar_one_or_none()
    if not news:
        raise HTTPException(status_code=404, detail="News not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(news, field, value)

    await db.commit()
    await db.refresh(news)
    return news
