import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_company, get_db, require_api_key
from app.models import TradeSignal
from app.models.enums import SignalStatusEnum
from app.schemas import TradeSignalCreate, TradeSignalResponse, TradeSignalUpdate

router = APIRouter(tags=["signals"])


@router.get("/companies/{ticker}/signals", response_model=list[TradeSignalResponse])
async def list_company_signals(
    ticker: str,
    status: Optional[SignalStatusEnum] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    company = await get_company(ticker, db)
    stmt = select(TradeSignal).where(TradeSignal.company_id == company.id)

    if status is not None:
        stmt = stmt.where(TradeSignal.status == status)

    stmt = stmt.order_by(TradeSignal.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/companies/{ticker}/signals",
    response_model=TradeSignalResponse,
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
async def create_signal(
    ticker: str,
    data: TradeSignalCreate,
    db: AsyncSession = Depends(get_db),
):
    company = await get_company(ticker, db)
    signal = TradeSignal(company_id=company.id, **data.model_dump())
    db.add(signal)
    await db.commit()
    await db.refresh(signal)
    return signal


@router.put(
    "/signals/{signal_id}",
    response_model=TradeSignalResponse,
    dependencies=[Depends(require_api_key)],
)
async def update_signal(
    signal_id: int,
    data: TradeSignalUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(TradeSignal).where(TradeSignal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    update_data = data.model_dump(exclude_unset=True)

    # When closing a signal, auto-set closed_at if not provided
    if "status" in update_data and update_data["status"] in (
        SignalStatusEnum.closed,
        SignalStatusEnum.expired,
    ):
        if signal.status == SignalStatusEnum.active and "closed_at" not in update_data:
            update_data["closed_at"] = dt.datetime.now(dt.UTC).replace(tzinfo=None)

    for field, value in update_data.items():
        setattr(signal, field, value)

    await db.commit()
    await db.refresh(signal)
    return signal
