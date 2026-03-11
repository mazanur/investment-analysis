import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import CatalystTypeEnum, ImpactEnum, MagnitudeEnum


class CatalystCreate(BaseModel):
    company_id: Optional[int] = None
    type: CatalystTypeEnum
    impact: ImpactEnum
    magnitude: MagnitudeEnum = MagnitudeEnum.medium
    date: Optional[dt.date] = None
    description: str
    source: Optional[str] = None
    trigger_tags: Optional[list[str]] = None
    is_active: bool = True


class CatalystUpdate(BaseModel):
    type: Optional[CatalystTypeEnum] = None
    impact: Optional[ImpactEnum] = None
    magnitude: Optional[MagnitudeEnum] = None
    date: Optional[dt.date] = None
    description: Optional[str] = None
    source: Optional[str] = None
    trigger_tags: Optional[list[str]] = None
    is_active: Optional[bool] = None


class CatalystResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: Optional[int] = None
    type: CatalystTypeEnum
    impact: ImpactEnum
    magnitude: MagnitudeEnum
    date: Optional[dt.date] = None
    description: str
    source: Optional[str] = None
    trigger_tags: Optional[list[str]] = None
    is_active: bool
    expired_at: Optional[dt.datetime] = None
    created_at: dt.datetime
