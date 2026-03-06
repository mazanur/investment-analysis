import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_api_key
from app.models import Catalyst, Company
from app.schemas import CatalystCreate, CatalystResponse, CatalystUpdate

router = APIRouter(tags=["catalysts"])


async def _get_company(ticker: str, db: AsyncSession) -> Company:
    result = await db.execute(select(Company).where(Company.ticker == ticker))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("/companies/{ticker}/catalysts", response_model=list[CatalystResponse])
async def list_company_catalysts(
    ticker: str,
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    company = await _get_company(ticker, db)
    stmt = select(Catalyst).where(Catalyst.company_id == company.id)

    if is_active is not None:
        stmt = stmt.where(Catalyst.is_active.is_(is_active))

    stmt = stmt.order_by(Catalyst.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/companies/{ticker}/catalysts",
    response_model=CatalystResponse,
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
async def create_company_catalyst(
    ticker: str,
    data: CatalystCreate,
    db: AsyncSession = Depends(get_db),
):
    company = await _get_company(ticker, db)
    catalyst = Catalyst(company_id=company.id, **data.model_dump(exclude={"company_id"}))
    db.add(catalyst)
    await db.commit()
    await db.refresh(catalyst)
    return catalyst


@router.post(
    "/catalysts",
    response_model=CatalystResponse,
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
async def create_macro_catalyst(
    data: CatalystCreate,
    db: AsyncSession = Depends(get_db),
):
    catalyst = Catalyst(**data.model_dump())
    db.add(catalyst)
    await db.commit()
    await db.refresh(catalyst)
    return catalyst


@router.put(
    "/catalysts/{catalyst_id}",
    response_model=CatalystResponse,
    dependencies=[Depends(require_api_key)],
)
async def update_catalyst(
    catalyst_id: int,
    data: CatalystUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Catalyst).where(Catalyst.id == catalyst_id))
    catalyst = result.scalar_one_or_none()
    if not catalyst:
        raise HTTPException(status_code=404, detail="Catalyst not found")

    update_data = data.model_dump(exclude_unset=True)
    # When deactivating, set expired_at automatically
    if "is_active" in update_data and not update_data["is_active"] and catalyst.is_active:
        catalyst.expired_at = dt.datetime.now(dt.UTC)

    for field, value in update_data.items():
        setattr(catalyst, field, value)

    await db.commit()
    await db.refresh(catalyst)
    return catalyst
