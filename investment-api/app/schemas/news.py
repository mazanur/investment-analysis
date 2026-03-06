import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import ActionEnum, ImpactEnum, StrengthEnum


class NewsCreate(BaseModel):
    company_id: Optional[int] = None
    sector_id: Optional[int] = None
    date: dt.date
    title: str
    url: Optional[str] = None
    source: Optional[str] = None
    impact: Optional[ImpactEnum] = None
    strength: Optional[StrengthEnum] = None
    summary: Optional[str] = None
    action: Optional[ActionEnum] = None


class NewsUpdate(BaseModel):
    impact: Optional[ImpactEnum] = None
    strength: Optional[StrengthEnum] = None
    summary: Optional[str] = None
    action: Optional[ActionEnum] = None


class NewsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: Optional[int] = None
    sector_id: Optional[int] = None
    date: dt.date
    title: str
    url: Optional[str] = None
    source: Optional[str] = None
    impact: Optional[ImpactEnum] = None
    strength: Optional[StrengthEnum] = None
    summary: Optional[str] = None
    action: Optional[ActionEnum] = None
    created_at: dt.datetime
