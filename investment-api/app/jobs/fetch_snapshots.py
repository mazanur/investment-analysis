"""
Fetch intraday price snapshots from MOEX ISS.

Takes a snapshot of current prices (LAST) and cumulative daily volume (VALTODAY)
for all tracked companies. Runs hourly during trading hours (10:00-19:00 MSK).

Reuses fetch_all_tqbr() from fetch_moex — single batch request for all tickers.

Author: AlmazNurmukhametov
"""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.fetch_moex import fetch_all_tqbr
from app.models import Company
from app.models.price_snapshot import PriceSnapshot

logger = logging.getLogger(__name__)

RETENTION_DAYS = 30


async def run_fetch_snapshots(db: AsyncSession) -> dict:
    """
    Fetch current prices from MOEX ISS and save as snapshots.

    Returns:
        dict with results: {"snapshots": int, "skipped": int}
    """
    result = {"snapshots": 0, "skipped": 0}

    companies_result = await db.execute(select(Company))
    companies = {c.ticker: c for c in companies_result.scalars().all()}

    if not companies:
        return result

    async with httpx.AsyncClient() as client:
        moex_data = await fetch_all_tqbr(client)

    if not moex_data:
        return result

    now = datetime.now(UTC).replace(tzinfo=None)

    for ticker, company in companies.items():
        md = moex_data.get(ticker)
        if not md or not md.get("last"):
            result["skipped"] += 1
            continue

        snapshot = PriceSnapshot(
            company_id=company.id,
            timestamp=now,
            price=Decimal(str(md["last"])),
            volume_rub=Decimal(str(md["valtoday"])) if md.get("valtoday") else None,
        )
        db.add(snapshot)
        result["snapshots"] += 1

    await db.commit()

    # Retention: delete snapshots older than 30 days
    cutoff = now - timedelta(days=RETENTION_DAYS)
    await db.execute(
        delete(PriceSnapshot).where(PriceSnapshot.timestamp < cutoff)
    )
    await db.commit()

    return result
