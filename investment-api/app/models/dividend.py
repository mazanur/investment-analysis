from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import DividendStatusEnum


class Dividend(Base):
    __tablename__ = "dividends"
    __table_args__ = (UniqueConstraint("company_id", "record_date", name="uq_dividend_company_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    record_date: Mapped[date]
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(10), default="RUB")
    yield_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    period_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[DividendStatusEnum] = mapped_column(default=DividendStatusEnum.announced)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC).replace(tzinfo=None))

    company: Mapped["Company"] = relationship(back_populates="dividends")  # noqa: F821
