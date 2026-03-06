from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_api_key
from app.models import Company, FinancialReport
from app.models.enums import PeriodTypeEnum
from app.schemas import FinancialReportCreate, FinancialReportResponse

router = APIRouter(tags=["financial-reports"])


async def _get_company(ticker: str, db: AsyncSession) -> Company:
    result = await db.execute(select(Company).where(Company.ticker == ticker))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("/companies/{ticker}/reports", response_model=list[FinancialReportResponse])
async def list_reports(
    ticker: str,
    period_type: Optional[PeriodTypeEnum] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    company = await _get_company(ticker, db)
    stmt = select(FinancialReport).where(FinancialReport.company_id == company.id)

    if period_type:
        stmt = stmt.where(FinancialReport.period_type == period_type)

    stmt = stmt.order_by(FinancialReport.period.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/companies/{ticker}/reports/latest", response_model=FinancialReportResponse)
async def get_latest_report(
    ticker: str,
    period_type: Optional[PeriodTypeEnum] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    company = await _get_company(ticker, db)
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
    company = await _get_company(ticker, db)

    # Upsert by (company_id, period)
    result = await db.execute(
        select(FinancialReport).where(
            FinancialReport.company_id == company.id,
            FinancialReport.period == data.period,
        )
    )
    report = result.scalar_one_or_none()

    if report:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(report, field, value)
    else:
        report = FinancialReport(company_id=company.id, **data.model_dump())
        db.add(report)

    await db.commit()
    await db.refresh(report)
    return report
