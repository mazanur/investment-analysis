"""
Fetch market snapshot from MOEX ISS API.

Ports logic from scripts/download_moex.py:
- Fetches current price, volume, capitalization for all TQBR securities
- Updates companies table (current_price, market_cap, adv_rub_mln, shares_out)
- Calculates ADV (30-day average daily value) and bid-ask spread

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

from app.models import Company

logger = logging.getLogger(__name__)

MOEX_TIMEOUT = 30.0
MOEX_BASE = "https://iss.moex.com/iss"

SECURITIES_URL = (
    f"{MOEX_BASE}/engines/stock/markets/shares/boardgroups/57"
    "/securities/{{ticker}}.json?iss.meta=off&iss.json=extended&lang=ru"
)

TQBR_ALL_URL = (
    f"{MOEX_BASE}/engines/stock/markets/shares/boards/TQBR"
    "/securities.json?iss.meta=off&iss.json=extended&start={{start}}"
)

CANDLES_URL = (
    f"{MOEX_BASE}/engines/stock/markets/shares/boards/TQBR"
    "/securities/{{ticker}}/candles.json"
    "?iss.meta=off&iss.json=extended&interval=24"
    "&from={{date_from}}&till={{date_till}}&lang=ru"
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


def _parse_tqbr_all(data: list) -> dict[str, dict]:
    """Parse batch TQBR response into {ticker: {last, open, high, low, valtoday, issuecap}}."""
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
                        "bid": row.get("BID", 0),
                        "offer": row.get("OFFER", 0),
                    })

    return result


def _parse_candles(data: list) -> list[dict]:
    """Parse candles response into list of {date, open, close, high, low, value}."""
    candles = []
    if not data or not isinstance(data, list):
        return candles

    for block in data:
        if not isinstance(block, dict):
            continue
        candles_block = block.get("candles")
        if candles_block and isinstance(candles_block, list):
            for row in candles_block:
                if isinstance(row, dict):
                    candles.append({
                        "date": row.get("begin", "")[:10],
                        "open": row.get("open", 0),
                        "close": row.get("close", 0),
                        "high": row.get("high", 0),
                        "low": row.get("low", 0),
                        "value": row.get("value", 0),
                    })
    return candles


def _calculate_adv(candles: list[dict], days: int = 30) -> float:
    """Calculate Average Daily Value (ADV) over last N trading days."""
    valid = [c for c in candles if c.get("value", 0) > 0]
    recent = valid[-days:] if len(valid) > days else valid
    if not recent:
        return 0
    return sum(c["value"] for c in recent) / len(recent)


async def fetch_all_tqbr(client: httpx.AsyncClient) -> dict[str, dict]:
    """Fetch all TQBR securities, paginating through all pages."""
    combined: dict[str, dict] = {}
    start = 0
    while True:
        url = TQBR_ALL_URL.format(start=start)
        data = await _fetch_json(client, url)
        if not data:
            break
        page = _parse_tqbr_all(data)
        if not page:
            break
        prev_size = len(combined)
        for ticker, info in page.items():
            combined.setdefault(ticker, {}).update(info)
        # Stop if no new tickers were added (last page or duplicate data)
        if len(combined) == prev_size:
            break
        start += len(page)
    return combined


async def run_fetch_moex(db: AsyncSession, tickers: list[str] | None = None) -> dict:
    """
    Main job: fetch market data from MOEX and update companies table.

    Args:
        db: Database session
        tickers: Optional list of tickers to update. If None, updates all companies in DB.

    Returns:
        dict with results: {"updated": int, "not_found": int, "errors": list[str]}
    """
    result = {"updated": 0, "not_found": 0, "errors": []}

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
        # Batch fetch all TQBR data
        moex_data = await fetch_all_tqbr(client)

        if not moex_data:
            result["errors"].append("Failed to fetch data from MOEX ISS")
            return result

        for ticker, company in companies.items():
            md = moex_data.get(ticker)
            if not md or not md.get("last"):
                result["not_found"] += 1
                continue

            # Update company fields
            company.current_price = Decimal(str(md["last"]))

            issuecap = md.get("issuecap", 0)
            if issuecap:
                company.market_cap = Decimal(str(issuecap))

            issuesize = md.get("issuesize", 0)
            if issuesize:
                company.shares_out = issuesize

            # Calculate ADV from candles (last 60 days to get ~30 trading days)
            date_till = date.today().isoformat()
            date_from = (date.today() - timedelta(days=60)).isoformat()
            candles_url = CANDLES_URL.format(
                ticker=ticker, date_from=date_from, date_till=date_till
            )
            candles_data = await _fetch_json(client, candles_url)
            candles = _parse_candles(candles_data) if candles_data else []

            adv = _calculate_adv(candles, 30)
            if adv > 0:
                company.adv_rub_mln = Decimal(str(round(adv / 1_000_000, 1)))

            result["updated"] += 1

    await db.commit()
    return result
