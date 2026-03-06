import datetime as dt
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PriceCreate(BaseModel):
    date: dt.date
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Decimal
    volume_rub: Optional[Decimal] = None
    market_cap: Optional[Decimal] = None


class PriceBulkCreate(BaseModel):
    prices: list[PriceCreate]


class PriceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    date: dt.date
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Decimal
    volume_rub: Optional[Decimal] = None
    market_cap: Optional[Decimal] = None
    created_at: dt.datetime
