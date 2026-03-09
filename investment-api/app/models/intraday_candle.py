import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class IntradayCandle(Base):
    __tablename__ = "intraday_candles"
    __table_args__ = (
        UniqueConstraint("company_id", "timestamp", "interval", name="uq_intraday_company_ts_interval"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime)
    interval: Mapped[str] = mapped_column(String(10))
    open: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    high: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    low: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    close: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    volume: Mapped[int | None] = mapped_column(Integer, nullable=True)

    company: Mapped["Company"] = relationship(back_populates="intraday_candles")  # noqa: F821
