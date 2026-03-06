from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import PeriodTypeEnum


class FinancialReport(Base):
    __tablename__ = "financial_reports"
    __table_args__ = (UniqueConstraint("company_id", "period", "period_type", name="uq_report_company_period_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    period: Mapped[str] = mapped_column(String(20))
    period_type: Mapped[PeriodTypeEnum]
    report_date: Mapped[date | None] = mapped_column(nullable=True)
    net_income: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    equity: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_debt: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    net_debt: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    roe: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    eps: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    p_e: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    p_bv: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    extra_metrics: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC).replace(tzinfo=None))

    company: Mapped["Company"] = relationship(back_populates="financial_reports")  # noqa: F821
