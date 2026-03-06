import datetime
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Price(Base):
    __tablename__ = "prices"
    __table_args__ = (UniqueConstraint("company_id", "date", name="uq_price_company_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    date: Mapped[datetime.date] = mapped_column(Date)
    open: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    low: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    close: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    volume_rub: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))

    company: Mapped["Company"] = relationship(back_populates="prices")  # noqa: F821
