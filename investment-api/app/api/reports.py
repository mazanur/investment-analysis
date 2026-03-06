from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_company, get_db, require_api_key
from app.models import FinancialReport
from app.models.enums import PeriodTypeEnum
from app.schemas import FinancialReportCreate, FinancialReportResponse

router = APIRouter(tags=["financial-reports"])


@router.get("/companies/{ticker}/reports", response_model=list[FinancialReportResponse])
async def list_reports(
    ticker: str,
    period_type: Optional[PeriodTypeEnum] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    company = await get_company(ticker, db)
    stmt = select(FinancialReport).where(FinancialReport.company_id == company.id)

    if period_type:
        stmt = stmt.where(FinancialReport.period_type == period_type)

    stmt = stmt.order_by(FinancialReport.period.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/companies/{ticker}/reports/latest", response_model=FinancialReportResponse)
async def get_latest_report(
    ticker: str,
    period_type: Optional[PeriodTypeEnum] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    company = await get_company(ticker, db)
    stmt = select(FinancialReport).where(FinancialReport.company_id == company.id)

    if period_type:
        stmt = stmt.where(FinancialReport.period_type == period_type)

    stmt = stmt.order_by(FinancialReport.period.desc()).limit(1)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="No reports found")
    return report


@router.post(
    "/companies/{ticker}/reports",
    response_model=FinancialReportResponse,
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
async def upsert_report(
    ticker: str,
    data: FinancialReportCreate,
    db: AsyncSession = Depends(get_db),
):
    company = await get_company(ticker, db)

    # Atomic upsert using PostgreSQL INSERT ON CONFLICT
    values = {"company_id": company.id, **data.model_dump()}
    update_fields = data.model_dump(exclude={"period", "period_type"}, exclude_unset=True)
    stmt = pg_insert(FinancialReport).values(**values)
    if update_fields:
        stmt = stmt.on_conflict_do_update(
            constraint="uq_report_company_period_type",
            set_=update_fields,
        )
    else:
        stmt = stmt.on_conflict_do_nothing(constraint="uq_report_company_period_type")
    await db.execute(stmt)
    await db.commit()

    result = await db.execute(
        select(FinancialReport).where(
            FinancialReport.company_id == company.id,
            FinancialReport.period == data.period,
            FinancialReport.period_type == data.period_type,
        )
    )
    report = result.scalar_one_or_none()
    return report
