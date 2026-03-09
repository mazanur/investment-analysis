import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class OrderBookSnapshot(Base):
    __tablename__ = "order_book_snapshots"
    __table_args__ = (
        UniqueConstraint("company_id", "timestamp", name="uq_orderbook_company_ts"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime)
    best_bid: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    best_ask: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    spread_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    depth: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    company: Mapped["Company"] = relationship(back_populates="order_book_snapshots")  # noqa: F821
