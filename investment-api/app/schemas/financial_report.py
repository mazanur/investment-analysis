import datetime as dt
from decimal import Decimal
from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.enums import PeriodTypeEnum


class FinancialReportCreate(BaseModel):
    period: str
    period_type: PeriodTypeEnum
    report_date: Optional[dt.date] = None
    net_income: Optional[Decimal] = None
    revenue: Optional[Decimal] = None
    equity: Optional[Decimal] = None
    total_debt: Optional[Decimal] = None
    net_debt: Optional[Decimal] = None
    roe: Optional[Decimal] = None
    eps: Optional[Decimal] = None
    p_e: Optional[Decimal] = None
    p_bv: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None
    extra_metrics: Optional[dict[str, Union[float, int]]] = None

    @field_validator("extra_metrics")
    @classmethod
    def validate_extra_metrics(cls, v: Optional[dict]) -> Optional[dict]:
        if v is None:
            return v
        for key, val in v.items():
            if not isinstance(key, str):
                raise ValueError(f"extra_metrics keys must be strings, got {type(key)}")
            if not isinstance(val, (int, float)):
                raise ValueError(
                    f"extra_metrics values must be numbers, got {type(val)} for key '{key}'"
                )
        return v


class FinancialReportUpdate(BaseModel):
    report_date: Optional[dt.date] = None
    net_income: Optional[Decimal] = None
    revenue: Optional[Decimal] = None
    equity: Optional[Decimal] = None
    total_debt: Optional[Decimal] = None
    net_debt: Optional[Decimal] = None
    roe: Optional[Decimal] = None
    eps: Optional[Decimal] = None
    p_e: Optional[Decimal] = None
    p_bv: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None
    extra_metrics: Optional[dict[str, Union[float, int]]] = None

    @field_validator("extra_metrics")
    @classmethod
    def validate_extra_metrics(cls, v: Optional[dict]) -> Optional[dict]:
        if v is None:
            return v
        for key, val in v.items():
            if not isinstance(key, str):
                raise ValueError(f"extra_metrics keys must be strings, got {type(key)}")
            if not isinstance(val, (int, float)):
                raise ValueError(
                    f"extra_metrics values must be numbers, got {type(val)} for key '{key}'"
                )
        return v


class FinancialReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    period: str
    period_type: PeriodTypeEnum
    report_date: Optional[dt.date] = None
    net_income: Optional[Decimal] = None
    revenue: Optional[Decimal] = None
    equity: Optional[Decimal] = None
    total_debt: Optional[Decimal] = None
    net_debt: Optional[Decimal] = None
    roe: Optional[Decimal] = None
    eps: Optional[Decimal] = None
    p_e: Optional[Decimal] = None
    p_bv: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None
    extra_metrics: Optional[dict[str, Union[float, int]]] = None
    created_at: dt.datetime
