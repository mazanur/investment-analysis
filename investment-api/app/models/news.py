import datetime

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import ActionEnum, ImpactEnum, StrengthEnum


class News(Base):
    __tablename__ = "news"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    sector_id: Mapped[int | None] = mapped_column(ForeignKey("sectors.id"), nullable=True)
    date: Mapped[datetime.date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    impact: Mapped[ImpactEnum | None] = mapped_column(nullable=True)
    strength: Mapped[StrengthEnum | None] = mapped_column(nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[ActionEnum | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))

    company: Mapped["Company | None"] = relationship(back_populates="news")  # noqa: F821
    sector: Mapped["Sector | None"] = relationship(back_populates="news")  # noqa: F821
    trade_signals: Mapped[list["TradeSignal"]] = relationship(back_populates="news")  # noqa: F821
