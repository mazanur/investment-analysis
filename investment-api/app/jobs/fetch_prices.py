"""
Fetch OHLCV price history from MOEX ISS API.

Ports logic from scripts/update_prices.py:
- Batch-fetches daily candles for all companies
- Bulk upserts into prices table
- Supports backfill mode for historical data

MOEX ISS API is public, no auth required.

Author: AlmazNurmukhametov
"""

import asyncio
import logging
from datetime import date, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, Price

logger = logging.getLogger(__name__)

MOEX_TIMEOUT = 30.0
MOEX_BASE = "https://iss.moex.com/iss"

TQBR_ALL_URL = (
    MOEX_BASE + "/engines/stock/markets/shares/boards/TQBR"
    "/securities.json?iss.meta=off&iss.json=extended&start={start}"
)

CANDLES_URL = (
    MOEX_BASE + "/engines/stock/markets/shares/boards/TQBR"
    "/securities/{ticker}/candles.json"
    "?iss.meta=off&iss.json=extended&interval=24"
    "&from={date_from}&till={date_till}"
)


async def _fetch_json(client: httpx.AsyncClient, url: str) -> list | dict | None:
    """Fetch JSON from MOEX ISS API with retries and backoff."""
    for attempt in range(3):
        try:
            resp = await client.get(url, timeout=MOEX_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("MOEX fetch attempt %d failed: %s", attempt + 1, e)
            if attempt == 2:
                return None
            await asyncio.sleep(2**attempt)


def _parse_tqbr_snapshot(data: list) -> dict[str, dict]:
    """Parse batch TQBR response for today's prices."""
    result: dict[str, dict] = {}
    if not data or not isinstance(data, list):
        return result

    for block in data:
        if not isinstance(block, dict):
            continue

        securities = block.get("securities")
        if securities and isinstance(securities, list):
            for row in securities:
                if not isinstance(row, dict):
                    continue
                ticker = row.get("SECID", "")
                if ticker:
                    result.setdefault(ticker, {})
                    result[ticker]["issuesize"] = row.get("ISSUESIZE", 0)

        marketdata = block.get("marketdata")
        if marketdata and isinstance(marketdata, list):
            for row in marketdata:
                if not isinstance(row, dict):
                    continue
                ticker = row.get("SECID", "")
                if ticker:
                    result.setdefault(ticker, {})
                    result[ticker].update({
                        "last": row.get("LAST") or row.get("LCLOSEPRICE", 0),
                        "open": row.get("OPEN", 0),
                        "high": row.get("HIGH", 0),
                        "low": row.get("LOW", 0),
                        "valtoday": row.get("VALTODAY", 0),
                        "issuecap": row.get("ISSUECAPITALIZATION", 0),
                    })

    return result


def _parse_candles(data: list) -> list[dict]:
    """Parse candles response into list of OHLCV dicts."""
    candles = []
    if not data or not isinstance(data, list):
        return candles

    for block in data:
        if not isinstance(block, dict):
            continue
        candles_block = block.get("candles")
        if candles_block and isinstance(candles_block, list):
            for row in candles_block:
                if isinstance(row, dict) and row.get("close"):
                    candles.append({
                        "date": row.get("begin", "")[:10],
                        "close": row.get("close", 0),
                        "open": row.get("open", 0),
                        "high": row.get("high", 0),
                        "low": row.get("low", 0),
                        "volume_rub": int(row.get("value", 0)),
                    })
    return candles


async def _upsert_prices(
    db: AsyncSession,
    company_id: int,
    candles: list[dict],
    market_cap_by_date: dict[str, float] | None = None,
) -> int:
    """Upsert candles into prices table. Returns count of upserted rows."""
    if not candles:
        return 0

    dates = [c["date"] for c in candles]
    stmt = select(Price).where(
        Price.company_id == company_id,
        Price.date.in_([date.fromisoformat(d) for d in dates]),
    )
    result = await db.execute(stmt)
    existing = {p.date.isoformat(): p for p in result.scalars().all()}

    count = 0
    for candle in candles:
        d = candle["date"]
        mcap = (market_cap_by_date or {}).get(d)

        if d in existing:
            p = existing[d]
            p.open = Decimal(str(candle["open"]))
            p.high = Decimal(str(candle["high"]))
            p.low = Decimal(str(candle["low"]))
            p.close = Decimal(str(candle["close"]))
            p.volume_rub = Decimal(str(candle["volume_rub"]))
            if mcap:
                p.market_cap = Decimal(str(mcap))
        else:
            price = Price(
                company_id=company_id,
                date=date.fromisoformat(d),
                open=Decimal(str(candle["open"])),
                high=Decimal(str(candle["high"])),
                low=Decimal(str(candle["low"])),
                close=Decimal(str(candle["close"])),
                volume_rub=Decimal(str(candle["volume_rub"])),
                market_cap=Decimal(str(mcap)) if mcap else None,
            )
            db.add(price)
        count += 1

    return count


async def run_fetch_prices(
    db: AsyncSession,
    tickers: list[str] | None = None,
    backfill_days: int = 0,
) -> dict:
    """
    Main job: fetch prices from MOEX and upsert into prices table.

    Two modes:
    1. Default (backfill_days=0): fetch today's snapshot for all TQBR securities,
       write one row per company for today.
    2. Backfill (backfill_days>0): fetch candle history for each ticker,
       bulk upsert historical OHLCV data.

    Args:
        db: Database session
        tickers: Optional list of tickers. If None, updates all companies in DB.
        backfill_days: Number of days to backfill. 0 = today only.

    Returns:
        dict with results: {"updated": int, "not_found": int, "total_prices": int, "errors": list[str]}
    """
    result = {"updated": 0, "not_found": 0, "total_prices": 0, "errors": []}

    # Get companies from DB
    if tickers:
        stmt = select(Company).where(Company.ticker.in_(tickers))
    else:
        stmt = select(Company)
    companies_result = await db.execute(stmt)
    companies = {c.ticker: c for c in companies_result.scalars().all()}

    if not companies:
        result["errors"].append("No companies found in database")
        return result

    async with httpx.AsyncClient() as client:
        if backfill_days > 0:
            # Backfill mode: fetch candle history for each company
            result = await _backfill_prices(client, db, companies, backfill_days, result)
        else:
            # Snapshot mode: fetch today's data from TQBR batch endpoint
            result = await _snapshot_prices(client, db, companies, result)

    await db.commit()
    return result


async def _snapshot_prices(
    client: httpx.AsyncClient,
    db: AsyncSession,
    companies: dict[str, Company],
    result: dict,
) -> dict:
    """Fetch today's snapshot and write one price row per company."""
    moex_data: dict[str, dict] = {}
    start = 0
    while True:
        url = TQBR_ALL_URL.format(start=start)
        data = await _fetch_json(client, url)
        if not data:
            break
        page = _parse_tqbr_snapshot(data)
        if not page:
            break
        prev_size = len(moex_data)
        for ticker, info in page.items():
            moex_data.setdefault(ticker, {}).update(info)
        # Stop if no new tickers were added (last page or duplicate data)
        if len(moex_data) == prev_size:
            break
        start += len(page)

    if not moex_data:
        result["errors"].append("Failed to fetch TQBR snapshot from MOEX")
        return result

    today = date.today()
    for ticker, company in companies.items():
        md = moex_data.get(ticker)
        if not md or not md.get("last"):
            result["not_found"] += 1
            continue

        candle = {
            "date": today.isoformat(),
            "close": md["last"],
            "open": md.get("open", 0),
            "high": md.get("high", 0),
            "low": md.get("low", 0),
            "volume_rub": int(md.get("valtoday", 0)),
        }
        mcap = md.get("issuecap", 0)
        market_cap_by_date = {today.isoformat(): mcap} if mcap else None

        count = await _upsert_prices(db, company.id, [candle], market_cap_by_date)
        result["total_prices"] += count
        result["updated"] += 1

    return result


async def _backfill_prices(
    client: httpx.AsyncClient,
    db: AsyncSession,
    companies: dict[str, Company],
    days: int,
    result: dict,
) -> dict:
    """Fetch historical candles and bulk upsert for each company."""
    date_till = date.today().isoformat()
    date_from_dt = date.today() - timedelta(days=days)

    for ticker, company in companies.items():
        all_candles = []
        chunk_from = date_from_dt

        # Fetch in chunks of 499 days (MOEX ISS limit ~500 candles per request)
        while chunk_from.isoformat() < date_till:
            chunk_till = min(chunk_from + timedelta(days=499), date.today())
            url = CANDLES_URL.format(
                ticker=ticker,
                date_from=chunk_from.isoformat(),
                date_till=chunk_till.isoformat(),
            )
            data = await _fetch_json(client, url)
            candles = _parse_candles(data) if data else []
            all_candles.extend(candles)

            if chunk_till.isoformat() >= date_till:
                break
            chunk_from = chunk_till + timedelta(days=1)

        if not all_candles:
            result["not_found"] += 1
            continue

        count = await _upsert_prices(db, company.id, all_candles)
        result["total_prices"] += count
        result["updated"] += 1

    return result
