import datetime
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import (
    DirectionEnum,
    PositionSizeEnum,
    SignalEnum,
    SignalStatusEnum,
)


class TradeSignal(Base):
    __tablename__ = "trade_signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    news_id: Mapped[int | None] = mapped_column(ForeignKey("news.id"), nullable=True)
    date: Mapped[datetime.date] = mapped_column(Date)
    signal: Mapped[SignalEnum]
    direction: Mapped[DirectionEnum]
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    entry_condition: Mapped[str | None] = mapped_column(String(500), nullable=True)
    take_profit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    time_limit_days: Mapped[int | None] = mapped_column(nullable=True)
    expected_return_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    risk_reward: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    position_size: Mapped[PositionSizeEnum | None] = mapped_column(nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[SignalStatusEnum] = mapped_column(default=SignalStatusEnum.active)
    result_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    closed_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC).replace(tzinfo=None))

    company: Mapped["Company"] = relationship(back_populates="trade_signals")  # noqa: F821
    news: Mapped["News | None"] = relationship(back_populates="trade_signals")  # noqa: F821
