import datetime as dt
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.enums import (
    DirectionEnum,
    PositionSizeEnum,
    SignalEnum,
    SignalStatusEnum,
)


class TradeSignalCreate(BaseModel):
    news_id: Optional[int] = None
    date: dt.date
    signal: SignalEnum
    direction: DirectionEnum
    confidence: Decimal
    entry_price: Optional[Decimal] = None
    entry_condition: Optional[str] = None
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    time_limit_days: Optional[int] = None
    expected_return_pct: Optional[Decimal] = None
    risk_reward: Optional[Decimal] = None
    position_size: Optional[PositionSizeEnum] = None
    reasoning: Optional[str] = None
    status: SignalStatusEnum = SignalStatusEnum.active

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 100:
            raise ValueError("confidence must be between 0 and 100")
        return v

    @field_validator("risk_reward")
    @classmethod
    def validate_risk_reward(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("risk_reward must be >= 0")
        return v


class TradeSignalUpdate(BaseModel):
    status: Optional[SignalStatusEnum] = None
    result_pct: Optional[Decimal] = None
    closed_at: Optional[dt.datetime] = None


class TradeSignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    news_id: Optional[int] = None
    date: dt.date
    signal: SignalEnum
    direction: DirectionEnum
    confidence: Decimal
    entry_price: Optional[Decimal] = None
    entry_condition: Optional[str] = None
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    time_limit_days: Optional[int] = None
    expected_return_pct: Optional[Decimal] = None
    risk_reward: Optional[Decimal] = None
    position_size: Optional[PositionSizeEnum] = None
    reasoning: Optional[str] = None
    status: SignalStatusEnum
    result_pct: Optional[Decimal] = None
    closed_at: Optional[dt.datetime] = None
    created_at: dt.datetime
