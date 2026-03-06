from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_api_key
from app.models import Sector
from app.schemas import SectorCreate, SectorResponse, SectorUpdate

router = APIRouter(prefix="/sectors", tags=["sectors"])


@router.get("", response_model=list[SectorResponse])
async def list_sectors(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Sector).order_by(Sector.name))
    return result.scalars().all()


@router.get("/{slug}", response_model=SectorResponse)
async def get_sector(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Sector).where(Sector.slug == slug))
    sector = result.scalar_one_or_none()
    if not sector:
        raise HTTPException(status_code=404, detail="Sector not found")
    return sector


@router.post("", response_model=SectorResponse, status_code=201, dependencies=[Depends(require_api_key)])
async def create_sector(data: SectorCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Sector).where(Sector.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Sector with this slug already exists")
    sector = Sector(**data.model_dump())
    db.add(sector)
    await db.commit()
    await db.refresh(sector)
    return sector


@router.put("/{slug}", response_model=SectorResponse, dependencies=[Depends(require_api_key)])
async def update_sector(slug: str, data: SectorUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Sector).where(Sector.slug == slug))
    sector = result.scalar_one_or_none()
    if not sector:
        raise HTTPException(status_code=404, detail="Sector not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(sector, field, value)
    await db.commit()
    await db.refresh(sector)
    return sector
