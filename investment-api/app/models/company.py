from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import PositionEnum, SentimentEnum


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    sector_id: Mapped[int | None] = mapped_column(ForeignKey("sectors.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(300))
    subsector: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sentiment: Mapped[SentimentEnum | None] = mapped_column(nullable=True)
    position: Mapped[PositionEnum | None] = mapped_column(nullable=True)
    my_fair_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    upside: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    shares_out: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    free_float: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    adv_rub_mln: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    p_e: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    p_bv: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    roe: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    gov_ownership: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    figi: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    tinkoff_uid: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lot_size: Mapped[int | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    sector: Mapped["Sector | None"] = relationship(back_populates="companies")  # noqa: F821
    financial_reports: Mapped[list["FinancialReport"]] = relationship(back_populates="company")  # noqa: F821
    dividends: Mapped[list["Dividend"]] = relationship(back_populates="company")  # noqa: F821
    catalysts: Mapped[list["Catalyst"]] = relationship(back_populates="company")  # noqa: F821
    prices: Mapped[list["Price"]] = relationship(back_populates="company")  # noqa: F821
    news: Mapped[list["News"]] = relationship(back_populates="company")  # noqa: F821
    trade_signals: Mapped[list["TradeSignal"]] = relationship(back_populates="company")  # noqa: F821
    price_snapshots: Mapped[list["PriceSnapshot"]] = relationship(back_populates="company")  # noqa: F821
    order_book_snapshots: Mapped[list["OrderBookSnapshot"]] = relationship(back_populates="company")  # noqa: F821
    intraday_candles: Mapped[list["IntradayCandle"]] = relationship(back_populates="company")  # noqa: F821
