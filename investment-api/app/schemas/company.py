import datetime as dt
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import PositionEnum, SentimentEnum

from .catalyst import CatalystResponse
from .dividend import DividendResponse
from .price import PriceResponse


class CompanyCreate(BaseModel):
    ticker: str
    sector_id: Optional[int] = None
    name: str
    subsector: Optional[str] = None
    sentiment: Optional[SentimentEnum] = None
    position: Optional[PositionEnum] = None
    my_fair_value: Optional[Decimal] = None
    current_price: Optional[Decimal] = None
    upside: Optional[Decimal] = None
    market_cap: Optional[Decimal] = None
    shares_out: Optional[Decimal] = None
    free_float: Optional[Decimal] = None
    adv_rub_mln: Optional[Decimal] = None
    p_e: Optional[Decimal] = None
    p_bv: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None
    roe: Optional[Decimal] = None
    gov_ownership: Optional[Decimal] = None
    business_model: Optional[str] = None
    thesis: Optional[str] = None
    scenarios: Optional[str] = None


class CompanyUpdate(BaseModel):
    sector_id: Optional[int] = None
    name: Optional[str] = None
    subsector: Optional[str] = None
    sentiment: Optional[SentimentEnum] = None
    position: Optional[PositionEnum] = None
    my_fair_value: Optional[Decimal] = None
    current_price: Optional[Decimal] = None
    upside: Optional[Decimal] = None
    market_cap: Optional[Decimal] = None
    shares_out: Optional[Decimal] = None
    free_float: Optional[Decimal] = None
    adv_rub_mln: Optional[Decimal] = None
    p_e: Optional[Decimal] = None
    p_bv: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None
    roe: Optional[Decimal] = None
    gov_ownership: Optional[Decimal] = None
    business_model: Optional[str] = None
    thesis: Optional[str] = None
    scenarios: Optional[str] = None


class CompanyListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    sector_id: Optional[int] = None
    name: str
    subsector: Optional[str] = None
    sentiment: Optional[SentimentEnum] = None
    position: Optional[PositionEnum] = None
    my_fair_value: Optional[Decimal] = None
    current_price: Optional[Decimal] = None
    upside: Optional[Decimal] = None
    market_cap: Optional[Decimal] = None
    p_e: Optional[Decimal] = None
    p_bv: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None
    roe: Optional[Decimal] = None
    figi: Optional[str] = None
    lot_size: Optional[int] = None
    updated_at: dt.datetime


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    sector_id: Optional[int] = None
    name: str
    subsector: Optional[str] = None
    sentiment: Optional[SentimentEnum] = None
    position: Optional[PositionEnum] = None
    my_fair_value: Optional[Decimal] = None
    current_price: Optional[Decimal] = None
    upside: Optional[Decimal] = None
    market_cap: Optional[Decimal] = None
    shares_out: Optional[Decimal] = None
    free_float: Optional[Decimal] = None
    adv_rub_mln: Optional[Decimal] = None
    p_e: Optional[Decimal] = None
    p_bv: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None
    roe: Optional[Decimal] = None
    gov_ownership: Optional[Decimal] = None
    figi: Optional[str] = None
    lot_size: Optional[int] = None
    business_model: Optional[str] = None
    thesis: Optional[str] = None
    scenarios: Optional[str] = None
    updated_at: dt.datetime

    latest_price: Optional[PriceResponse] = None
    active_catalysts: list[CatalystResponse] = []
    last_dividend: Optional[DividendResponse] = None
