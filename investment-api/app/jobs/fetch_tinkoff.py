"""
Fetch market data from Tinkoff Invest REST API.

Provides:
- Instrument mapping (FIGI codes, lot sizes)
- Daily prices (backup source alongside MOEX)
- Order book snapshots (bid-ask spread, market depth)
- Intraday candles (15-min OHLCV)

REST API base: https://invest-public-api.tbank.ru/rest/
Auth: Bearer token from TINKOFF_TOKEN env var.
SSL verification disabled — Tinkoff uses self-signed intermediate cert.

Author: AlmazNurmukhametov
"""

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Company, Price

logger = logging.getLogger(__name__)

TINKOFF_BASE = "https://invest-public-api.tbank.ru/rest"
TINKOFF_TIMEOUT = 30.0


def _quotation_to_decimal(q: dict | None) -> Decimal | None:
    """Convert Tinkoff Quotation {units, nano} to Decimal."""
    if not q:
        return None
    units = int(q.get("units", 0) or 0)
    nano = int(q.get("nano", 0) or 0)
    if units == 0 and nano == 0:
        return None
    return Decimal(str(units)) + Decimal(str(nano)) / Decimal("1000000000")


async def _tinkoff_post(
    client: httpx.AsyncClient,
    path: str,
    body: dict | None = None,
) -> dict | None:
    """POST to Tinkoff REST API with retries and Bearer auth."""
    url = f"{TINKOFF_BASE}/{path}"
    headers = {"Authorization": f"Bearer {settings.tinkoff_token}"}
    for attempt in range(3):
        try:
            resp = await client.post(
                url,
                json=body or {},
                headers=headers,
                timeout=TINKOFF_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("Tinkoff fetch attempt %d failed for %s: %s", attempt + 1, path, e)
            if attempt == 2:
                return None
            await asyncio.sleep(2**attempt)


# ---------------------------------------------------------------------------
# Job 1: Instrument mapping
# ---------------------------------------------------------------------------


async def run_fetch_tinkoff_instruments(db: AsyncSession) -> dict:
    """
    Fetch all shares from Tinkoff and update companies with FIGI, uid, lot_size.

    Matches by ticker. Only updates companies already in the DB.
    Filters for MOEX-traded instruments (exchange contains 'moex').
    """
    result = {"matched": 0, "not_found": 0, "errors": []}

    if not settings.tinkoff_token:
        result["errors"].append("TINKOFF_TOKEN not configured")
        return result

    companies_result = await db.execute(select(Company))
    companies = {c.ticker: c for c in companies_result.scalars().all()}

    if not companies:
        result["errors"].append("No companies in database")
        return result

    async with httpx.AsyncClient(verify=False) as client:
        data = await _tinkoff_post(
            client,
            "tinkoff.public.invest.api.contract.v1.InstrumentsService/Shares",
            {"instrumentStatus": "INSTRUMENT_STATUS_BASE"},
        )

    if not data or "instruments" not in data:
        result["errors"].append("Failed to fetch instruments from Tinkoff")
        return result

    instruments = data["instruments"]

    # Build lookup by ticker for MOEX-traded shares
    tinkoff_by_ticker: dict[str, dict] = {}
    for inst in instruments:
        exchange = (inst.get("exchange") or "").lower()
        if "moex" not in exchange:
            continue
        t = inst.get("ticker", "")
        if t:
            tinkoff_by_ticker[t] = inst

    for ticker, company in companies.items():
        inst = tinkoff_by_ticker.get(ticker)
        if not inst:
            result["not_found"] += 1
            continue

        company.figi = inst.get("figi")
        company.tinkoff_uid = inst.get("uid")
        company.lot_size = int(inst.get("lot", 1))
        result["matched"] += 1

    await db.commit()
    logger.info(
        "Tinkoff instruments: matched=%d, not_found=%d",
        result["matched"],
        result["not_found"],
    )
    return result


# ---------------------------------------------------------------------------
# Job 2: Daily prices (backup)
# ---------------------------------------------------------------------------


async def run_fetch_tinkoff_prices(
    db: AsyncSession,
    tickers: list[str] | None = None,
    backfill_days: int = 0,
) -> dict:
    """
    Fetch daily candles from Tinkoff and upsert into prices table.

    Used as backup alongside MOEX prices. Uses COALESCE to only fill NULLs,
    never overwrites existing MOEX data.
    """
    result = {"updated": 0, "skipped_no_figi": 0, "total_prices": 0, "errors": []}

    if not settings.tinkoff_token:
        result["errors"].append("TINKOFF_TOKEN not configured")
        return result

    if tickers:
        stmt = select(Company).where(Company.ticker.in_(tickers))
    else:
        stmt = select(Company)
    companies_result = await db.execute(stmt)
    companies = list(companies_result.scalars().all())

    if not companies:
        result["errors"].append("No companies in database")
        return result

    days = backfill_days if backfill_days > 0 else 1
    now = datetime.now(UTC).replace(tzinfo=None)
    date_from = now - timedelta(days=days)

    async with httpx.AsyncClient(verify=False) as client:
        for company in companies:
            if not company.figi:
                result["skipped_no_figi"] += 1
                continue

            data = await _tinkoff_post(
                client,
                "tinkoff.public.invest.api.contract.v1.MarketDataService/GetCandles",
                {
                    "instrumentId": company.figi,
                    "from": date_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "interval": "CANDLE_INTERVAL_DAY",
                },
            )

            if not data or "candles" not in data:
                continue

            candles = data["candles"]
            if not candles:
                continue

            values = []
            for c in candles:
                close = _quotation_to_decimal(c.get("close"))
                if not close:
                    continue
                ts = (c.get("time") or "")[:10]
                if not ts:
                    continue
                values.append({
                    "company_id": company.id,
                    "date": date.fromisoformat(ts),
                    "open": _quotation_to_decimal(c.get("open")),
                    "high": _quotation_to_decimal(c.get("high")),
                    "low": _quotation_to_decimal(c.get("low")),
                    "close": close,
                    "volume_rub": None,
                })

            if not values:
                continue

            cols = Price.__table__.c
            insert_stmt = pg_insert(Price).values(values)
            insert_stmt = insert_stmt.on_conflict_do_update(
                constraint="uq_price_company_date",
                set_={
                    "open": func.coalesce(cols.open, insert_stmt.excluded.open),
                    "high": func.coalesce(cols.high, insert_stmt.excluded.high),
                    "low": func.coalesce(cols.low, insert_stmt.excluded.low),
                    "close": func.coalesce(cols.close, insert_stmt.excluded.close),
                },
            )
            await db.execute(insert_stmt)
            result["total_prices"] += len(values)
            result["updated"] += 1

            await asyncio.sleep(0.6)

    await db.commit()
    return result


# ---------------------------------------------------------------------------
# Job 3: Order book snapshots
# ---------------------------------------------------------------------------


async def run_fetch_tinkoff_orderbook(
    db: AsyncSession,
    tickers: list[str] | None = None,
) -> dict:
    """
    Fetch order book snapshots from Tinkoff for all companies with FIGI.

    Stores best bid/ask, spread, and full depth (20 levels).
    30-day retention.
    """
    from app.models.order_book_snapshot import OrderBookSnapshot

    result = {"snapshots": 0, "skipped_no_figi": 0, "errors": []}

    if not settings.tinkoff_token:
        result["errors"].append("TINKOFF_TOKEN not configured")
        return result

    if tickers:
        stmt = select(Company).where(Company.ticker.in_(tickers))
    else:
        stmt = select(Company)
    companies_result = await db.execute(stmt)
    companies = list(companies_result.scalars().all())

    now = datetime.now(UTC).replace(tzinfo=None)

    async with httpx.AsyncClient(verify=False) as client:
        for company in companies:
            if not company.figi:
                result["skipped_no_figi"] += 1
                continue

            data = await _tinkoff_post(
                client,
                "tinkoff.public.invest.api.contract.v1.MarketDataService/GetOrderBook",
                {"instrumentId": company.figi, "depth": 20},
            )

            if not data:
                continue

            bids_raw = data.get("bids", [])
            asks_raw = data.get("asks", [])

            best_bid = _quotation_to_decimal(bids_raw[0].get("price")) if bids_raw else None
            best_ask = _quotation_to_decimal(asks_raw[0].get("price")) if asks_raw else None

            spread_pct = None
            if best_bid and best_ask and best_bid > 0:
                spread_pct = ((best_ask - best_bid) / best_bid * 100).quantize(Decimal("0.0001"))

            depth = {
                "bids": [
                    {"price": str(_quotation_to_decimal(b.get("price"))), "qty": int(b.get("quantity", 0))}
                    for b in bids_raw
                ],
                "asks": [
                    {"price": str(_quotation_to_decimal(a.get("price"))), "qty": int(a.get("quantity", 0))}
                    for a in asks_raw
                ],
            }

            snapshot = OrderBookSnapshot(
                company_id=company.id,
                timestamp=now,
                best_bid=best_bid,
                best_ask=best_ask,
                spread_pct=spread_pct,
                depth=depth,
            )
            db.add(snapshot)
            result["snapshots"] += 1

            await asyncio.sleep(0.6)

    await db.commit()

    # Retention: delete snapshots older than 30 days
    cutoff = now - timedelta(days=30)
    await db.execute(
        delete(OrderBookSnapshot).where(OrderBookSnapshot.timestamp < cutoff)
    )
    await db.commit()

    return result


# ---------------------------------------------------------------------------
# Job 4: Intraday candles
# ---------------------------------------------------------------------------

INTERVAL_MAP = {
    "5min": "CANDLE_INTERVAL_5_MIN",
    "15min": "CANDLE_INTERVAL_15_MIN",
}


async def run_fetch_tinkoff_candles(
    db: AsyncSession,
    tickers: list[str] | None = None,
    interval: str = "15min",
) -> dict:
    """
    Fetch intraday candles from Tinkoff for all companies with FIGI.

    Fetches last 1 hour of candles at the specified interval.
    30-day retention.
    """
    from app.models.intraday_candle import IntradayCandle

    result = {"candles": 0, "companies": 0, "skipped_no_figi": 0, "errors": []}

    if not settings.tinkoff_token:
        result["errors"].append("TINKOFF_TOKEN not configured")
        return result

    tinkoff_interval = INTERVAL_MAP.get(interval)
    if not tinkoff_interval:
        result["errors"].append(f"Unknown interval: {interval}")
        return result

    if tickers:
        stmt = select(Company).where(Company.ticker.in_(tickers))
    else:
        stmt = select(Company)
    companies_result = await db.execute(stmt)
    companies = list(companies_result.scalars().all())

    now = datetime.now(UTC).replace(tzinfo=None)
    from_time = now - timedelta(hours=1)

    async with httpx.AsyncClient(verify=False) as client:
        for company in companies:
            if not company.figi:
                result["skipped_no_figi"] += 1
                continue

            data = await _tinkoff_post(
                client,
                "tinkoff.public.invest.api.contract.v1.MarketDataService/GetCandles",
                {
                    "instrumentId": company.figi,
                    "from": from_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "interval": tinkoff_interval,
                },
            )

            if not data or "candles" not in data:
                continue

            candles_data = data["candles"]
            if not candles_data:
                continue

            values = []
            for c in candles_data:
                close = _quotation_to_decimal(c.get("close"))
                if not close:
                    continue
                ts_str = c.get("time", "")
                if not ts_str:
                    continue
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
                values.append({
                    "company_id": company.id,
                    "timestamp": ts,
                    "interval": interval,
                    "open": _quotation_to_decimal(c.get("open")),
                    "high": _quotation_to_decimal(c.get("high")),
                    "low": _quotation_to_decimal(c.get("low")),
                    "close": close,
                    "volume": int(c.get("volume", 0)) if c.get("volume") else None,
                })

            if values:
                insert_stmt = pg_insert(IntradayCandle).values(values)
                insert_stmt = insert_stmt.on_conflict_do_update(
                    constraint="uq_intraday_company_ts_interval",
                    set_={
                        "open": insert_stmt.excluded.open,
                        "high": insert_stmt.excluded.high,
                        "low": insert_stmt.excluded.low,
                        "close": insert_stmt.excluded.close,
                        "volume": insert_stmt.excluded.volume,
                    },
                )
                await db.execute(insert_stmt)
                result["candles"] += len(values)
                result["companies"] += 1

            await asyncio.sleep(0.6)

    await db.commit()

    # Retention: delete candles older than 30 days
    cutoff = now - timedelta(days=30)
    await db.execute(
        delete(IntradayCandle).where(IntradayCandle.timestamp < cutoff)
    )
    await db.commit()

    return result
