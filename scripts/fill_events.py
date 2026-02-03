#!/usr/bin/env python3
"""
Генерирует events.md для компаний из скачанных данных MOEX ISS.

Читает companies/{TICKER}/data/moex_events.json и генерирует events.md
с таблицами последних событий и предстоящих катализаторов.
Сохраняет ручные секции (Guidance, IR-презентации, Санкционный статус).

Использование:
    python3 scripts/fill_events.py              # все компании
    python3 scripts/fill_events.py SBER LKOH    # конкретные тикеры

Автор: AlmazNurmukhametov
"""

import json
import os
import re
import sys
from datetime import date, datetime, timedelta


# Цвета для вывода
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
NC = "\033[0m"

# Русские месяцы для парсинга дат из macro.md
RU_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

# Классификация влияния по типу события
EVENT_IMPACT = {
    "Публикация отчетности": "зависит от результатов",
    "IR событие (online)": "нейтрально",
    "IR событие (очное)": "нейтрально",
    "Выплаты по инструментам": "позитив",
    "Собрания владельцев ценных бумаг": "нейтрально",
}

# Секции events.md: автоматические (перезаписываются) и ручные (сохраняются)
MANUAL_SECTIONS = [
    "Guidance менеджмента",
    "Ключевые выдержки из IR-презентаций",
    "Санкционный статус",
]


def parse_yaml_frontmatter(content: str) -> dict:
    """Парсит простой YAML frontmatter из markdown-файла."""
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    yaml_content = match.group(1)
    result = {}

    for line in yaml_content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([a-zA-Z][a-zA-Z0-9_-]*):\s*(.*)$", line)
        if m:
            key = m.group(1)
            value = m.group(2).strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            result[key] = value

    return result


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


def read_company_name(ticker: str, companies_dir: str) -> str:
    """Читает название компании из _index.md."""
    index_file = os.path.join(companies_dir, ticker, "_index.md")
    if os.path.exists(index_file):
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                content = f.read(1000)
                meta = parse_yaml_frontmatter(content)
                return meta.get("name", ticker)
        except OSError:
            pass
    return ticker


def read_cb_meetings(base_dir: str) -> list[str]:
    """
    Читает даты заседаний ЦБ из russia/macro.md.

    Возвращает список дат в формате YYYY-MM-DD (только будущие).
    """
    macro_path = os.path.join(base_dir, "russia", "macro.md")
    if not os.path.exists(macro_path):
        return []

    try:
        with open(macro_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return []

    # Ищем секцию "Ближайшие заседания ЦБ"
    match = re.search(
        r"##\s*Ближайшие заседания ЦБ\s*\n(.*?)(?:\n##|\Z)",
        content,
        re.DOTALL,
    )
    if not match:
        return []

    dates = []
    today = date.today()

    for line in match.group(1).split("\n"):
        line = line.strip()
        if not line.startswith("|") or "---" in line or "Дата" in line:
            continue

        # Парсим "| 13 февраля 2026 | комментарий |"
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 2:
            continue

        date_str = cells[1]
        m = re.match(r"(\d{1,2})\s+(\w+)\s+(\d{4})", date_str)
        if m:
            day = int(m.group(1))
            month_name = m.group(2).lower()
            year = int(m.group(3))
            month = RU_MONTHS.get(month_name)
            if month:
                try:
                    d = date(year, month, day)
                    if d >= today:
                        dates.append(d.isoformat())
                except ValueError:
                    pass

    return dates


def parse_existing_manual_sections(filepath: str) -> dict[str, str]:
    """
    Извлекает ручные секции из существующего events.md.

    Возвращает dict: {"Guidance менеджмента": "содержимое", ...}
    """
    result = {s: "" for s in MANUAL_SECTIONS}

    if not os.path.exists(filepath):
        return result

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return result

    # Разбиваем по ## заголовкам
    sections = re.split(r"\n(?=## )", content)

    for section in sections:
        for name in MANUAL_SECTIONS:
            if section.strip().startswith(f"## {name}"):
                # Берём всё после заголовка
                lines = section.split("\n", 1)
                if len(lines) > 1:
                    result[name] = lines[1]
                break

    return result


def format_past_events_table(
    ir_events: list[dict], dividends: list[dict]
) -> str:
    """Формирует таблицу последних событий за 6 месяцев."""
    today = date.today()
    cutoff = (today - timedelta(days=180)).isoformat()
    today_str = today.isoformat()

    rows = []

    # Прошлые IR-события
    for e in ir_events:
        d = e.get("event_date", "")
        if cutoff <= d < today_str:
            impact = EVENT_IMPACT.get(e.get("event_type", ""), "нейтрально")
            desc = e.get("description", e.get("event_type", ""))
            rows.append((d, desc, impact, "MOEX ISS"))

    # Прошлые дивиденды
    for d in dividends:
        close_date = d.get("registryclosedate", "")
        if cutoff <= close_date < today_str:
            value = d.get("value", 0)
            currency = d.get("currencyid", "RUB")
            rows.append((
                close_date,
                f"Дивидендная отсечка: {value} {currency}",
                "позитив",
                "MOEX ISS",
            ))

    # Сортировка по дате: новые сверху
    rows.sort(key=lambda r: r[0], reverse=True)

    lines = [
        "| Дата | Событие | Влияние | Источник |",
        "|------|---------|---------|----------|",
    ]

    if rows:
        for d, event, impact, source in rows:
            lines.append(f"| {d} | {event} | {impact} | {source} |")
    else:
        lines.append("| | Нет данных за последние 6 месяцев | | |")

    return "\n".join(lines)


def format_future_events_table(
    ir_events: list[dict],
    dividends: list[dict],
    cb_meetings: list[str],
) -> str:
    """Формирует таблицу предстоящих катализаторов."""
    today_str = date.today().isoformat()

    rows = []

    # Будущие IR-события
    for e in ir_events:
        d = e.get("event_date", "")
        if d >= today_str:
            impact = EVENT_IMPACT.get(e.get("event_type", ""), "нейтрально")
            desc = e.get("description", e.get("event_type", ""))
            rows.append((d, desc, impact))

    # Будущие дивиденды
    for d in dividends:
        close_date = d.get("registryclosedate", "")
        if close_date >= today_str:
            value = d.get("value", 0)
            currency = d.get("currencyid", "RUB")
            rows.append((
                close_date,
                f"Дивидендная отсечка: {value} {currency}",
                "позитив",
            ))

    # Заседания ЦБ
    for cb_date in cb_meetings:
        rows.append((cb_date, "Заседание ЦБ (влияет на сектор)", "зависит от решения"))

    # Сортировка по дате: ближайшие сверху
    rows.sort(key=lambda r: r[0])

    lines = [
        "| Дата (ожид.) | Событие | Ожидаемое влияние |",
        "|--------------|---------|-------------------|",
    ]

    if rows:
        for d, event, impact in rows:
            lines.append(f"| {d} | {event} | {impact} |")
    else:
        lines.append("| | Нет предстоящих событий | |")

    return "\n".join(lines)


def default_guidance_section() -> str:
    """Шаблон секции Guidance менеджмента."""
    return """
Прогнозы менеджмента из последних конференц-звонков и презентаций.

| Параметр | Прогноз менеджмента | Источник | Дата |
|----------|---------------------|----------|------|
| Рост выручки 20XX | | | |
| Маржа EBITDA 20XX | | | |
| CAPEX 20XX | | | |
| Дивидендная политика | | | |
| Долговая стратегия | | | |
"""


def default_ir_section() -> str:
    """Шаблон секции IR-презентаций."""
    return """
### Последняя презентация (дата, название)

Основные тезисы:
1.
2.
3.
"""


def default_sanctions_section() -> str:
    """Шаблон секции санкционного статуса."""
    return """
| Параметр | Значение |
|----------|----------|
| SDN (OFAC) | да/нет |
| ЕС sanctions | да/нет |
| UK sanctions | да/нет |
| Вторичные санкции | риск для контрагентов да/нет |
| Влияние на бизнес | описание |
"""


def generate_events_md(
    ticker: str,
    company_name: str,
    events_data: dict,
    cb_meetings: list[str],
    manual_sections: dict[str, str],
) -> str:
    """Собирает полный events.md."""
    ir_events = events_data.get("ir_events", [])
    dividends = events_data.get("dividends", [])

    past_table = format_past_events_table(ir_events, dividends)
    future_table = format_future_events_table(ir_events, dividends, cb_meetings)

    # Ручные секции: используем существующие или дефолтный шаблон
    guidance = manual_sections.get("Guidance менеджмента", "")
    if not guidance.strip():
        guidance = default_guidance_section()

    ir_pres = manual_sections.get("Ключевые выдержки из IR-презентаций", "")
    if not ir_pres.strip():
        ir_pres = default_ir_section()

    sanctions = manual_sections.get("Санкционный статус", "")
    if not sanctions.strip():
        sanctions = default_sanctions_section()

    return f"""---
ticker: {ticker}
updated: {date.today().isoformat()}
---

# Корпоративные события: {company_name} ({ticker})

IR-материалы, пресс-релизы и предстоящие катализаторы.
Таблицы событий обновляются автоматически: `make download-events TICKER={ticker} && make fill-events TICKER={ticker}`.

## Последние события (6 месяцев)

{past_table}

## Предстоящие катализаторы

{future_table}

## Guidance менеджмента
{guidance}
## Ключевые выдержки из IR-презентаций
{ir_pres}
## Санкционный статус
{sanctions}"""


def process_company(
    ticker: str, companies_dir: str, cb_meetings: list[str]
) -> dict:
    """
    Генерирует events.md для одной компании.

    Возвращает {"ok": bool, "skipped": bool, "past": int, "future": int}
    """
    result = {"ok": False, "skipped": False, "past": 0, "future": 0}

    events_file = os.path.join(companies_dir, ticker, "data", "moex_events.json")
    if not os.path.exists(events_file):
        result["skipped"] = True
        return result

    try:
        with open(events_file, "r", encoding="utf-8") as f:
            events_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return result

    company_name = read_company_name(ticker, companies_dir)

    events_md_path = os.path.join(companies_dir, ticker, "events.md")
    manual_sections = parse_existing_manual_sections(events_md_path)

    content = generate_events_md(
        ticker, company_name, events_data, cb_meetings, manual_sections
    )

    with open(events_md_path, "w", encoding="utf-8") as f:
        f.write(content)
        f.write("\n")

    # Считаем статистику
    today_str = date.today().isoformat()
    cutoff = (date.today() - timedelta(days=180)).isoformat()

    for e in events_data.get("ir_events", []):
        d = e.get("event_date", "")
        if cutoff <= d < today_str:
            result["past"] += 1
        elif d >= today_str:
            result["future"] += 1

    for d in events_data.get("dividends", []):
        close_date = d.get("registryclosedate", "")
        if cutoff <= close_date < today_str:
            result["past"] += 1
        elif close_date >= today_str:
            result["future"] += 1

    result["future"] += len(cb_meetings)
    result["ok"] = True
    return result


def main():
    """Основная функция."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    companies_dir = os.path.join(base_dir, "companies")

    if not os.path.exists(companies_dir):
        print(f"{RED}Ошибка: директория {companies_dir} не найдена{NC}")
        return 1

    # Парсим аргументы
    args = sys.argv[1:]
    if args:
        tickers = [t.upper() for t in args]
        for t in tickers:
            if not os.path.isdir(os.path.join(companies_dir, t)):
                print(f"{RED}Ошибка: папка companies/{t} не найдена{NC}")
                return 1
    else:
        tickers = get_tickers(companies_dir)

    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print(f"{CYAN}  Генерация events.md ({date.today().isoformat()}){NC}")
    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print()
    print(f"  Компаний: {len(tickers)}")

    # Загружаем даты заседаний ЦБ
    cb_meetings = read_cb_meetings(base_dir)
    if cb_meetings:
        print(f"  Заседания ЦБ: {len(cb_meetings)} предстоящих")
    print()

    ok = 0
    skipped = 0
    failed = 0

    for i, ticker in enumerate(tickers, 1):
        prefix = f"  [{i}/{len(tickers)}] {ticker}"

        result = process_company(ticker, companies_dir, cb_meetings)

        if result["skipped"]:
            print(
                f"{prefix}: {YELLOW}пропуск (нет data/moex_events.json — "
                f"запустите make download-events){NC}"
            )
            skipped += 1
        elif result["ok"]:
            print(
                f"{prefix}: {GREEN}OK{NC} — "
                f"прошлых: {result['past']}, будущих: {result['future']}"
            )
            ok += 1
        else:
            print(f"{prefix}: {RED}ошибка чтения данных{NC}")
            failed += 1

    print()
    print(
        f"Готово: {GREEN}{ok} OK{NC}, "
        f"{YELLOW}{skipped} пропущено{NC}, "
        f"{RED}{failed} ошибок{NC}"
    )

    return 0


if __name__ == "__main__":
    exit(main())
