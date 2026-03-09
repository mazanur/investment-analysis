import datetime as dt
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import DividendStatusEnum


class DividendCreate(BaseModel):
    record_date: dt.date
    amount: Decimal
    currency: str = "RUB"
    yield_pct: Optional[Decimal] = None
    period_label: Optional[str] = None
    status: DividendStatusEnum = DividendStatusEnum.announced


class DividendUpdate(BaseModel):
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    yield_pct: Optional[Decimal] = None
    period_label: Optional[str] = None
    status: Optional[DividendStatusEnum] = None


class DividendResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    record_date: dt.date
    amount: Decimal
    currency: str
    yield_pct: Optional[Decimal] = None
    period_label: Optional[str] = None
    status: DividendStatusEnum
    created_at: dt.datetime
