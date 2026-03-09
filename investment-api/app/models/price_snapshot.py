import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    __table_args__ = (
        UniqueConstraint("company_id", "timestamp", name="uq_snapshot_company_ts"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    volume_rub: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)

    company: Mapped["Company"] = relationship(back_populates="price_snapshots")  # noqa: F821
