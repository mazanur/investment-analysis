import datetime

from sqlalchemy import Date, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import CatalystTypeEnum, ImpactEnum, MagnitudeEnum


class Catalyst(Base):
    __tablename__ = "catalysts"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    type: Mapped[CatalystTypeEnum]
    impact: Mapped[ImpactEnum]
    magnitude: Mapped[MagnitudeEnum] = mapped_column(default=MagnitudeEnum.medium)
    date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    expired_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC).replace(tzinfo=None))

    company: Mapped["Company | None"] = relationship(back_populates="catalysts")  # noqa: F821
