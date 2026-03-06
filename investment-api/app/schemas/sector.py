import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SectorCreate(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None


class SectorUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class SectorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    description: Optional[str] = None
    updated_at: dt.datetime
