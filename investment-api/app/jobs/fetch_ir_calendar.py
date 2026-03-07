"""
Fetch IR calendar events from MOEX ISS API.

Ports logic from scripts/download_moex_events.py:
- Fetches the global IR calendar (paginated)
- Matches events to companies in DB by name
- Upserts as Catalyst records (type="event")

MOEX ISS API is public, no auth required.

Author: AlmazNurmukhametov
"""

import asyncio
import logging
import re
from datetime import date, datetime, UTC

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company
from app.models.catalyst import Catalyst
from app.models.enums import CatalystTypeEnum, ImpactEnum, MagnitudeEnum

logger = logging.getLogger(__name__)

MOEX_TIMEOUT = 30.0
MOEX_BASE = "https://iss.moex.com/iss"
MAX_PAGES = 100

IR_CALENDAR_URL = (
    MOEX_BASE + "/cci/calendars/ir-calendar.json"
    "?iss.meta=off&iss.json=extended&start={start}"
)

SOURCE_TAG = "moex_ir_calendar"

# Map MOEX event types to impact
EVENT_IMPACT_MAP: dict[str, ImpactEnum] = {
    "Публикация отчетности": ImpactEnum.mixed,
    "IR событие (online)": ImpactEnum.neutral,
    "IR событие (очное)": ImpactEnum.neutral,
    "Выплаты по инструментам": ImpactEnum.positive,
    "Собрания владельцев ценных бумаг": ImpactEnum.neutral,
}


async def _fetch_json(client: httpx.AsyncClient, url: str) -> list | dict | None:
    """Fetch JSON from MOEX ISS API with retries."""
    for attempt in range(3):
        try:
            resp = await client.get(url, timeout=MOEX_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("MOEX IR calendar fetch attempt %d failed: %s", attempt + 1, e)
            if attempt == 2:
                return None
            await asyncio.sleep(2**attempt)


async def _fetch_all_ir_events(client: httpx.AsyncClient) -> list[dict]:
    """Fetch all IR calendar events with pagination."""
    all_events: list[dict] = []
    start = 0

    for _ in range(MAX_PAGES):
        data = await _fetch_json(client, IR_CALENDAR_URL.format(start=start))
        if not data:
            break

        page_events: list[dict] = []
        for block in data:
            if not isinstance(block, dict):
                continue
            events = block.get("cci_ir_calendar", [])
            if not events or not isinstance(events, list):
                continue
            for e in events:
                if not isinstance(e, dict):
                    continue
                page_events.append({
                    "company_name": e.get("company_name_full_ru", ""),
                    "inn": e.get("inn", ""),
                    "event_date": (e.get("event_date") or "")[:10],
                    "event_type": e.get("event_type_name", ""),
                    "description": e.get("event_description", ""),
                    "link": e.get("event_link", ""),
                })

        all_events.extend(page_events)

        if len(page_events) < 100:
            break

        start += 100
        await asyncio.sleep(0.3)

    return all_events


def _match_events_for_company(
    all_events: list[dict], company_name: str
) -> list[dict]:
    """Match IR events to a company by name (fuzzy substring match)."""
    matched = []
    name_lower = company_name.lower()

    if len(company_name) < 4:
        # Short names: word-boundary match to avoid false positives
        pattern = re.compile(
            r'(?:^|[\s"«\'(])' + re.escape(name_lower) + r'(?:[\s"»\').,]|$)',
            re.IGNORECASE,
        )
        for event in all_events:
            if pattern.search(event.get("company_name", "")):
                matched.append(event)
    else:
        for event in all_events:
            if name_lower in event.get("company_name", "").lower():
                matched.append(event)

    return matched


async def _deactivate_past_events(db: AsyncSession) -> int:
    """Deactivate IR calendar catalysts that are past today."""
    today = date.today()
    stmt = select(Catalyst).where(
        and_(
            Catalyst.source == SOURCE_TAG,
            Catalyst.is_active.is_(True),
            Catalyst.date < today,
        )
    )
    result = await db.execute(stmt)
    catalysts = result.scalars().all()

    count = 0
    now = datetime.now(UTC).replace(tzinfo=None)
    for cat in catalysts:
        cat.is_active = False
        cat.expired_at = now
        count += 1

    return count


async def _upsert_events(
    db: AsyncSession,
    company_id: int,
    events: list[dict],
) -> int:
    """Upsert IR calendar events as Catalyst records."""
    if not events:
        return 0

    today = date.today()

    # Load existing catalysts for this company from IR calendar
    stmt = select(Catalyst).where(
        and_(
            Catalyst.company_id == company_id,
            Catalyst.source == SOURCE_TAG,
        )
    )
    result = await db.execute(stmt)
    existing = {}
    for cat in result.scalars().all():
        key = (cat.date, cat.description)
        existing[key] = cat

    count = 0
    for event in events:
        event_date_str = event.get("event_date", "")
        if not event_date_str:
            continue

        try:
            event_date = date.fromisoformat(event_date_str[:10])
        except (ValueError, TypeError):
            continue

        event_type = event.get("event_type", "")
        description = event.get("description", "") or event_type
        if not description:
            continue

        impact = EVENT_IMPACT_MAP.get(event_type, ImpactEnum.neutral)
        is_active = event_date >= today

        key = (event_date, description)

        if key in existing:
            cat = existing[key]
            cat.impact = impact
            cat.is_active = is_active
            if not is_active and cat.expired_at is None:
                cat.expired_at = datetime.now(UTC).replace(tzinfo=None)
        else:
            cat = Catalyst(
                company_id=company_id,
                type=CatalystTypeEnum.event,
                impact=impact,
                magnitude=MagnitudeEnum.medium,
                date=event_date,
                description=description,
                source=SOURCE_TAG,
                is_active=is_active,
            )
            if not is_active:
                cat.expired_at = datetime.now(UTC).replace(tzinfo=None)
            db.add(cat)
        count += 1

    return count


async def run_fetch_ir_calendar(db: AsyncSession) -> dict:
    """
    Main job: fetch IR calendar from MOEX ISS and upsert as Catalyst records.

    Returns:
        dict with results: {"total_events": int, "matched_companies": int,
                           "upserted": int, "deactivated": int, "errors": list[str]}
    """
    result = {
        "total_events": 0,
        "matched_companies": 0,
        "upserted": 0,
        "deactivated": 0,
        "errors": [],
    }

    # Load all companies
    companies_result = await db.execute(select(Company))
    companies = companies_result.scalars().all()

    if not companies:
        result["errors"].append("No companies found in database")
        return result

    # Fetch IR calendar
    async with httpx.AsyncClient() as client:
        all_events = await _fetch_all_ir_events(client)

    if not all_events:
        result["errors"].append("No events fetched from MOEX IR calendar")
        return result

    result["total_events"] = len(all_events)

    # Match events to companies and upsert
    for company in companies:
        matched = _match_events_for_company(all_events, company.name)
        if not matched:
            continue

        result["matched_companies"] += 1
        count = await _upsert_events(db, company.id, matched)
        result["upserted"] += count

    # Deactivate past events
    deactivated = await _deactivate_past_events(db)
    result["deactivated"] = deactivated

    await db.commit()
    return result