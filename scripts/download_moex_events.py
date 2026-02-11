#!/usr/bin/env python3
"""
Загрузка событий и дивидендов с MOEX ISS API.

Скачивает дивиденды и IR-календарь (отчётность, ГОСА, IR-события),
сохраняет в companies/{TICKER}/data/moex_events.json.

MOEX ISS API — публичный, не требует авторизации.

Использование:
    python3 scripts/download_moex_events.py              # все компании
    python3 scripts/download_moex_events.py SBER LKOH    # конкретные тикеры
    python3 scripts/download_moex_events.py --force       # перезаписать существующие

Автор: AlmazNurmukhametov
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import date


# Настройки
DELAY_SECONDS = 0.5
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
MAX_CALENDAR_PAGES = 100  # защита от бесконечной пагинации

# MOEX ISS API endpoints
DIVIDENDS_URL = (
    "http://iss.moex.com/iss/securities/{ticker}/dividends.json"
    "?iss.meta=off&iss.json=extended"
)
IR_CALENDAR_URL = (
    "http://iss.moex.com/iss/cci/calendars/ir-calendar.json"
    "?iss.meta=off&iss.json=extended&start={start}"
)

# Цвета для вывода
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
NC = "\033[0m"


def fetch_json(url: str) -> dict | list | None:
    """Загружает JSON по URL. Возвращает parsed JSON или None."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            return json.loads(data)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        print(f"    {RED}Ошибка: {e}{NC}")
        return None
    except json.JSONDecodeError:
        return None


def get_tickers(companies_dir: str) -> list[str]:
    """Возвращает список тикеров из папки companies/."""
    tickers = []
    for name in sorted(os.listdir(companies_dir)):
        path = os.path.join(companies_dir, name)
        if not os.path.isdir(path):
            continue
        if name.startswith("_") or name.startswith("."):
            continue
        index_file = os.path.join(path, "_index.md")
        if os.path.exists(index_file):
            with open(index_file, "r", encoding="utf-8") as f:
                content = f.read(500)
                if "status: delisted" in content or "delisted: true" in content:
                    continue
        tickers.append(name)
    return tickers


def fetch_ir_calendar() -> list[dict]:
    """
    Загружает весь IR-календарь с пагинацией.

    Возвращает плоский список событий.
    """
    all_events = []
    start = 0

    print(f"  {CYAN}Загрузка IR-календаря...{NC}", end="", flush=True)

    for _ in range(MAX_CALENDAR_PAGES):
        data = fetch_json(IR_CALENDAR_URL.format(start=start))
        if not data:
            break

        page_events = []
        for block in data:
            if isinstance(block, dict):
                events = block.get("cci_ir_calendar", [])
                if events and isinstance(events, list):
                    for e in events:
                        if isinstance(e, dict):
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
        time.sleep(DELAY_SECONDS)

    print(f" {GREEN}{len(all_events)} событий{NC}")
    return all_events


def parse_dividends(data: list) -> list[dict]:
    """Парсит ответ dividends endpoint."""
    dividends = []
    if not data or not isinstance(data, list):
        return dividends

    for block in data:
        if not isinstance(block, dict):
            continue
        divs = block.get("dividends")
        if divs and isinstance(divs, list):
            for d in divs:
                if isinstance(d, dict):
                    dividends.append({
                        "registryclosedate": d.get("registryclosedate", ""),
                        "value": d.get("value", 0),
                        "currencyid": d.get("currencyid", ""),
                    })

    return dividends


def get_shortname(ticker: str, companies_dir: str) -> str:
    """
    Получает короткое имя компании для матчинга.

    Приоритет: moex_market.json → _index.md (name) → ticker.
    """
    # Из moex_market.json
    market_file = os.path.join(companies_dir, ticker, "data", "moex_market.json")
    if os.path.exists(market_file):
        try:
            with open(market_file, "r", encoding="utf-8") as f:
                market = json.load(f)
                name = market.get("shortname", "")
                if name:
                    return name
        except (json.JSONDecodeError, OSError):
            pass

    # Из _index.md
    index_file = os.path.join(companies_dir, ticker, "_index.md")
    if os.path.exists(index_file):
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                content = f.read(1000)
                match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
                if match:
                    return match.group(1).strip()
        except OSError:
            pass

    return ticker


def match_ir_events(
    all_events: list[dict], shortname: str
) -> list[dict]:
    """
    Находит IR-события для компании по shortname.

    Для коротких имён (<4 символов) — поиск по границе слова.
    """
    matched = []
    name_lower = shortname.lower()

    if len(shortname) < 4:
        # Для коротких имён: поиск по границе слова, чтобы "ВК" не матчился с "БАНКОВСКИЙ"
        pattern = re.compile(
            r'(?:^|[\s"«\'(])' + re.escape(name_lower) + r'(?:[\s"»\').,]|$)',
            re.IGNORECASE,
        )
        for event in all_events:
            company = event.get("company_name", "")
            if pattern.search(company):
                matched.append(event)
    else:
        for event in all_events:
            company = event.get("company_name", "").lower()
            if name_lower in company:
                matched.append(event)

    return matched


def download_company(
    ticker: str,
    companies_dir: str,
    all_ir_events: list[dict],
    force: bool = False,
) -> dict:
    """
    Скачивает данные о событиях для одной компании.

    Возвращает dict с результатами:
        {"ok": True/False, "skipped": True/False, "data": dict}
    """
    data_dir = os.path.join(companies_dir, ticker, "data")
    os.makedirs(data_dir, exist_ok=True)

    output_path = os.path.join(data_dir, "moex_events.json")
    result = {"ok": False, "skipped": False, "data": None}

    # Пропускаем если файл уже обновлён сегодня
    if not force and os.path.exists(output_path):
        today = date.today().isoformat()
        file_date = date.fromtimestamp(os.path.getmtime(output_path)).isoformat()
        if file_date == today:
            result["skipped"] = True
            return result

    # 1. Дивиденды
    div_data = fetch_json(DIVIDENDS_URL.format(ticker=ticker))
    dividends = parse_dividends(div_data) if div_data else []
    time.sleep(DELAY_SECONDS)

    # 2. Матчинг IR-событий
    shortname = get_shortname(ticker, companies_dir)
    ir_events = match_ir_events(all_ir_events, shortname)

    # 3. Собираем результат
    events_data = {
        "ticker": ticker,
        "company_name": shortname,
        "date": date.today().isoformat(),
        "dividends": dividends,
        "ir_events": ir_events,
    }

    # Сохраняем
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(events_data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    result["ok"] = True
    result["data"] = events_data
    return result


def main():
    """Основная функция."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    companies_dir = os.path.join(os.path.dirname(script_dir), "companies")

    if not os.path.exists(companies_dir):
        print(f"{RED}Ошибка: директория {companies_dir} не найдена{NC}")
        return 1

    # Парсим аргументы
    args = sys.argv[1:]
    force = "--force" in args
    args = [a for a in args if a != "--force"]

    if args:
        tickers = [t.upper() for t in args]
        for t in tickers:
            if not os.path.isdir(os.path.join(companies_dir, t)):
                print(f"{RED}Ошибка: папка companies/{t} не найдена{NC}")
                return 1
    else:
        tickers = get_tickers(companies_dir)

    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print(f"{CYAN}  Загрузка событий с MOEX ISS ({date.today().isoformat()}){NC}")
    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print()
    print(f"  Компаний: {len(tickers)}")
    if force:
        print(f"  {YELLOW}Режим --force: перезаписываем существующие{NC}")
    print()

    # Загружаем IR-календарь один раз
    all_ir_events = fetch_ir_calendar()
    print()

    ok = 0
    skipped = 0
    failed = 0

    for i, ticker in enumerate(tickers, 1):
        prefix = f"  [{i}/{len(tickers)}] {ticker}"

        result = download_company(ticker, companies_dir, all_ir_events, force=force)

        if result["skipped"]:
            print(f"{prefix}: {YELLOW}пропуск (уже обновлено сегодня){NC}")
            skipped += 1
        elif result["ok"]:
            d = result["data"]
            n_div = len(d["dividends"])
            n_ev = len(d["ir_events"])
            print(
                f"{prefix}: {GREEN}OK{NC} — "
                f"дивиденды: {n_div}, IR-события: {n_ev}"
            )
            ok += 1
        else:
            print(f"{prefix}: {RED}нет данных{NC}")
            failed += 1

    print()
    print(
        f"Готово: {GREEN}{ok} OK{NC}, "
        f"{YELLOW}{skipped} пропущено{NC}, "
        f"{RED}{failed} без данных{NC}"
    )

    return 0


if __name__ == "__main__":
    exit(main())
