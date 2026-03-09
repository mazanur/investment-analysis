from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import PositionEnum, SentimentEnum


class TopUpsideItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    name: str
    sector_slug: Optional[str] = None
    sentiment: Optional[SentimentEnum] = None
    position: Optional[PositionEnum] = None
    current_price: Optional[Decimal] = None
    my_fair_value: Optional[Decimal] = None
    upside: Optional[Decimal] = None


class ScreenerItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    name: str
    sector_slug: Optional[str] = None
    sentiment: Optional[SentimentEnum] = None
    position: Optional[PositionEnum] = None
    current_price: Optional[Decimal] = None
    upside: Optional[Decimal] = None
    p_e: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None
    roe: Optional[Decimal] = None
    market_cap: Optional[Decimal] = None


class SectorSummaryItem(BaseModel):
    slug: str
    name: str
    company_count: int
    bullish_count: int
    neutral_count: int
    bearish_count: int
    avg_upside: Optional[Decimal] = None


class OverdueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    name: str
    sector_slug: Optional[str] = None
    updated_at: str
    days_since_update: int
