import datetime as dt
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PriceSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    timestamp: dt.datetime
    price: Decimal
    volume_rub: Optional[Decimal] = None
