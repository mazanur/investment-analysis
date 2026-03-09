import datetime as dt
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class OrderBookSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    timestamp: dt.datetime
    best_bid: Optional[Decimal] = None
    best_ask: Optional[Decimal] = None
    spread_pct: Optional[Decimal] = None
    depth: Optional[dict[str, Any]] = None
