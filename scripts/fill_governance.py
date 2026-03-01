#!/usr/bin/env python3
"""
Генерирует governance.md для компаний из скачанных данных.

Читает:
- companies/{TICKER}/data/moex_events.json — дивиденды MOEX ISS
- companies/{TICKER}/data/smartlab_yearly.csv — финансовые показатели (payout ratio)
- companies/{TICKER}/data/sanctions.json — санкционный скрининг OpenSanctions

Генерирует авто-секции: «Дивидендная история», «Санкционный скрининг».
Сохраняет ручные секции: «Структура акционеров», «Дивидендная политика»,
«Программа buyback», «Менеджмент», «Риски», «GOD-дисконт».

Использование:
    python3 scripts/fill_governance.py              # все компании
    python3 scripts/fill_governance.py SBER LKOH    # конкретные тикеры

Автор: AlmazNurmukhametov
"""

import csv
import io
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date


# Цвета для вывода
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
NC = "\033[0m"

# Ручные секции — сохраняются при перегенерации
MANUAL_SECTIONS = [
    "Структура акционеров",
    "Дивидендная политика",
    "Программа buyback",
    "Менеджмент",
    "Риски корпоративного управления",
    "Расчёт GOD-дисконта",
]


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
                match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
                if match:
                    return match.group(1).strip()
        except OSError:
            pass
    return ticker


def read_dividends(ticker: str, companies_dir: str) -> list[dict]:
    """Читает дивиденды из moex_events.json."""
    path = os.path.join(companies_dir, ticker, "data", "moex_events.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("dividends", [])
    except (json.JSONDecodeError, OSError):
        return []


def read_sanctions(ticker: str, companies_dir: str) -> dict | None:
    """Читает санкционные данные из sanctions.json."""
    path = os.path.join(companies_dir, ticker, "data", "sanctions.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def read_smartlab_payout(ticker: str, companies_dir: str) -> dict[str, float]:
    """
    Читает payout ratio из smartlab_yearly.csv.

    Smart-lab CSV: разделитель ;, первая колонка — показатель, остальные — годы.
    Ищем строку содержащую 'payout' или 'дивиденд/прибыль'.

    Возвращает dict: {"2023": 50.0, "2024": 55.0, ...}
    """
    path = os.path.join(companies_dir, ticker, "data", "smartlab_yearly.csv")
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return {}

    result = {}
    reader = csv.reader(io.StringIO(content), delimiter=";")
    headers = []

    for row in reader:
        if not row:
            continue

        # Первая непустая строка — заголовки с годами
        if not headers:
            headers = row
            continue

        metric = row[0].strip().lower()

        # Ищем строку с payout ratio
        if "payout" in metric or "дивиденд/прибыль" in metric or "коэфф" in metric:
            for i, val in enumerate(row[1:], 1):
                if i < len(headers):
                    year = headers[i].strip()
                    try:
                        parsed = float(
                            val.replace(",", ".").replace("%", "").strip()
                        )
                        if parsed > 0:
                            result[year] = parsed
                    except (ValueError, AttributeError):
                        pass
            break

    return result


def analyze_dividends(dividends: list[dict]) -> dict:
    """
    Анализирует историю дивидендов.

    Возвращает:
    - by_year: {year: [payments]}
    - year_totals: {year: total_per_year}
    - consecutive_years: лет подряд (до текущего)
    - total_years: сколько всего лет платили
    - frequency: периодичность (1/2/4 раза в год)
    - first_year, last_year
    """
    empty = {
        "by_year": {},
        "year_totals": {},
        "consecutive_years": 0,
        "total_years": 0,
        "frequency": "—",
        "first_year": "—",
        "last_year": "—",
    }

    if not dividends:
        return empty

    # Группируем по году
    by_year = defaultdict(list)
    for d in dividends:
        close_date = d.get("registryclosedate", "")
        if not close_date or len(close_date) < 4:
            continue
        year = close_date[:4]
        value = d.get("value", 0)
        if value and value > 0:
            by_year[year].append({
                "date": close_date,
                "value": value,
                "currency": d.get("currencyid", "RUB"),
            })

    if not by_year:
        return empty

    years_sorted = sorted(by_year.keys())

    # Consecutive years (с последнего года выплаты назад)
    consecutive = 0
    last_year = int(years_sorted[-1])
    for y in range(last_year, int(years_sorted[0]) - 1, -1):
        if str(y) in by_year:
            consecutive += 1
        else:
            break

    # Средняя частота выплат в год
    payments_per_year = [len(by_year[y]) for y in years_sorted]
    avg_frequency = sum(payments_per_year) / len(payments_per_year)

    if avg_frequency >= 3.5:
        frequency = "4 раза в год"
    elif avg_frequency >= 1.5:
        frequency = "2 раза в год"
    else:
        frequency = "1 раз в год"

    # Суммы по годам
    year_totals = {}
    for year, payments in by_year.items():
        year_totals[year] = sum(p["value"] for p in payments)

    return {
        "by_year": dict(by_year),
        "year_totals": year_totals,
        "consecutive_years": consecutive,
        "total_years": len(by_year),
        "frequency": frequency,
        "first_year": years_sorted[0],
        "last_year": years_sorted[-1],
    }


# ─── Форматирование авто-секций ──────────────────────────────────────────────


def format_dividend_history(
    dividends: list[dict],
    analysis: dict,
    payout_data: dict[str, float],
    ticker: str,
) -> str:
    """Формирует секцию «Дивидендная история»."""
    if not dividends:
        return (
            f"\n*Нет данных о дивидендах. "
            f"Скачайте: `make download-events TICKER={ticker}`*\n"
        )

    lines = []

    # Сводка
    lines.append(
        f"**Периодичность:** {analysis['frequency']}"
    )
    lines.append(
        f"**Стабильность выплат:** платили {analysis['consecutive_years']} лет подряд "
        f"(всего {analysis['total_years']} лет с {analysis['first_year']})"
    )
    lines.append("")

    # Таблица по годам
    lines.append("| Год | Дивиденд на акцию | Выплат в году | Payout ratio |")
    lines.append("|-----|-------------------|---------------|--------------|")

    year_totals = analysis.get("year_totals", {})
    by_year = analysis.get("by_year", {})

    for year in sorted(year_totals.keys(), reverse=True):
        total = year_totals[year]
        count = len(by_year.get(year, []))
        currency = "RUB"
        if by_year.get(year):
            currency = by_year[year][0].get("currency", "RUB")

        payout = payout_data.get(year, None)
        payout_str = f"{payout:.0f}%" if payout is not None else "—"

        lines.append(f"| {year} | {total:.2f} {currency} | {count} | {payout_str} |")

    lines.append("")

    # Последние 10 выплат (детальная таблица)
    sorted_divs = sorted(
        dividends,
        key=lambda d: d.get("registryclosedate", ""),
        reverse=True,
    )
    recent = sorted_divs[:10]

    if recent:
        lines.append("### Последние выплаты")
        lines.append("")
        lines.append("| Дата закрытия реестра | Дивиденд | Валюта |")
        lines.append("|----------------------|----------|--------|")
        for d in recent:
            close_date = d.get("registryclosedate", "—")
            value = d.get("value", 0)
            currency = d.get("currencyid", "RUB")
            lines.append(f"| {close_date} | {value:.2f} | {currency} |")

    lines.append("")
    return "\n".join(lines)


def format_sanctions_screening(sanctions_data: dict | None, ticker: str) -> str:
    """Формирует секцию «Санкционный скрининг»."""
    if sanctions_data is None:
        return (
            f"\n*Нет данных. "
            f"Скачайте: `make download-governance TICKER={ticker}`*\n"
        )

    lines = []
    query = sanctions_data.get("query", "")
    scan_date = sanctions_data.get("date", "")
    total = sanctions_data.get("total", 0)
    relevant = sanctions_data.get("relevant_matches", 0)
    results = sanctions_data.get("results", [])

    lines.append(
        f"*Автоматический скрининг OpenSanctions "
        f"(запрос: «{query}», дата: {scan_date})*"
    )
    lines.append("")

    if relevant > 0:
        lines.append(f"**Результат: найдено {relevant} совпадений**")
        lines.append("")
        lines.append("| Имя | Тип | Датасеты | Score |")
        lines.append("|-----|-----|----------|-------|")
        for r in results:
            if r.get("score", 0) > 0.7:
                caption = r.get("caption", "—")
                schema = r.get("schema", "—")
                datasets = ", ".join(r.get("datasets", [])[:5])
                score = r.get("score", 0)
                lines.append(f"| {caption} | {schema} | {datasets} | {score:.2f} |")
    else:
        lines.append(
            f"**Результат: совпадений не найдено** (проверено {total} записей)"
        )

    lines.append("")
    lines.append("*Проверьте вручную для точности: SDN (OFAC), ЕС, UK списки.*")
    lines.append("")
    return "\n".join(lines)


# ─── Дефолтные шаблоны ручных секций ─────────────────────────────────────────


def default_shareholders_section() -> str:
    return """
| Акционер | Доля, % | Тип |
|----------|---------|-----|
| | | Государство / Частный / Менеджмент / Free-float |
| | | |
| | | |
| Free-float | | |

**Доля государства (прямая + косвенная):** X%
**Казначейские акции:** X% (есть ли план по гашению?)
"""


def default_dividend_policy_section() -> str:
    return """
**Текст политики:** (скопировать из устава / решения совета директоров)

> "Цитата из дивидендной политики компании"

| Параметр | Значение |
|----------|----------|
| Payout ratio (цель) | X% от ЧП МСФО/РСБУ |
| Дата ГОСА (обычно) | месяц |
| Реестр (обычно) | через X дней после ГОСА |
"""


def default_buyback_section() -> str:
    return """
| Параметр | Значение |
|----------|----------|
| Объявлена | да/нет |
| Объём | X млрд ₽ / X% капитализации |
| Срок | до 20XX |
| Выкуплено к дате | X млрд ₽ |
| Цель | гашение / казначейский пакет / мотивация менеджмента |
"""


def default_management_section() -> str:
    return """
| Должность | Имя | С какого года | Комментарий |
|-----------|-----|---------------|-------------|
| CEO | | | |
| CFO | | | |
| Председатель СД | | | |

**KPI менеджмента привязаны к капитализации?** да/нет
**Менеджмент владеет акциями?** да (X%) / нет
"""


def default_risks_section() -> str:
    return """
- [ ] Допэмиссии за последние 5 лет (размытие)
- [ ] Сделки с аффилированными лицами
- [ ] Смена аудитора
- [ ] Задержка публикации отчётности
- [ ] Казначейские акции > 10% без плана гашения
"""


def default_god_section() -> str:
    return """
(заполняет Claude на основе данных выше)

| Фактор | Значение | Дисконт |
|--------|----------|---------|
| Гос. владение > 50%? | да/нет | |
| Payout | X% | базовый: X% |
| Казначейские > 20%? | да/нет | X% |
| Рост дивидендов > 3 лет? | да/нет | X% |
| Менеджмент-чиновники? | да/нет | X% |
| **Итого GOD** | | **X%** |
"""


# ─── Сохранение ручных секций ─────────────────────────────────────────────────


def parse_existing_manual_sections(filepath: str) -> dict[str, str]:
    """
    Извлекает ручные секции из существующего governance.md.

    Возвращает dict: {"Структура акционеров": "содержимое", ...}
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


# ─── Генерация файла ──────────────────────────────────────────────────────────


def generate_governance_md(
    ticker: str,
    company_name: str,
    dividends: list[dict],
    div_analysis: dict,
    payout_data: dict[str, float],
    sanctions_data: dict | None,
    manual_sections: dict[str, str],
) -> str:
    """Собирает полный governance.md."""

    # Ручные секции: существующие или дефолтные
    shareholders = manual_sections.get("Структура акционеров", "")
    if not shareholders.strip():
        shareholders = default_shareholders_section()

    div_policy = manual_sections.get("Дивидендная политика", "")
    if not div_policy.strip():
        div_policy = default_dividend_policy_section()

    buyback = manual_sections.get("Программа buyback", "")
    if not buyback.strip():
        buyback = default_buyback_section()

    management = manual_sections.get("Менеджмент", "")
    if not management.strip():
        management = default_management_section()

    risks = manual_sections.get("Риски корпоративного управления", "")
    if not risks.strip():
        risks = default_risks_section()

    god = manual_sections.get("Расчёт GOD-дисконта", "")
    if not god.strip():
        god = default_god_section()

    # Авто-секции
    div_history = format_dividend_history(
        dividends, div_analysis, payout_data, ticker
    )
    sanctions = format_sanctions_screening(sanctions_data, ticker)

    return f"""---
ticker: {ticker}
updated: {date.today().isoformat()}
---

# Корпоративное управление: {company_name} ({ticker})

Данные для расчёта GOD-дисконта и оценки рисков корпоративного управления.
Автоматические секции обновляются: `make download-governance TICKER={ticker} && make fill-governance TICKER={ticker}`.

## Структура акционеров
{shareholders}
## Дивидендная политика
{div_policy}
## Дивидендная история

{div_history}
## Программа buyback
{buyback}
## Менеджмент
{management}
## Санкционный скрининг

{sanctions}
## Риски корпоративного управления
{risks}
## Расчёт GOD-дисконта
{god}"""


# ─── Обработка компаний ──────────────────────────────────────────────────────


def process_company(ticker: str, companies_dir: str) -> dict:
    """
    Генерирует governance.md для одной компании.

    Возвращает {"ok": bool, "skipped": bool, "n_dividends": int, "sanctions": bool}
    """
    result = {"ok": False, "skipped": False, "n_dividends": 0, "sanctions": False}

    # Нужен хотя бы один источник данных
    events_file = os.path.join(companies_dir, ticker, "data", "moex_events.json")
    sanctions_file = os.path.join(companies_dir, ticker, "data", "sanctions.json")

    if not os.path.exists(events_file) and not os.path.exists(sanctions_file):
        result["skipped"] = True
        return result

    company_name = read_company_name(ticker, companies_dir)

    # Читаем данные
    dividends = read_dividends(ticker, companies_dir)
    sanctions_data = read_sanctions(ticker, companies_dir)
    payout_data = read_smartlab_payout(ticker, companies_dir)

    # Анализ дивидендов
    div_analysis = analyze_dividends(dividends)

    # Сохраняем ручные секции из существующего файла
    governance_path = os.path.join(companies_dir, ticker, "governance.md")
    manual_sections = parse_existing_manual_sections(governance_path)

    # Генерируем
    content = generate_governance_md(
        ticker, company_name, dividends, div_analysis,
        payout_data, sanctions_data, manual_sections,
    )

    with open(governance_path, "w", encoding="utf-8") as f:
        f.write(content)
        f.write("\n")

    result["ok"] = True
    result["n_dividends"] = len(dividends)
    result["sanctions"] = (
        sanctions_data is not None
        and sanctions_data.get("relevant_matches", 0) > 0
    )
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
    if args:
        tickers = [t.upper() for t in args]
        for t in tickers:
            if not os.path.isdir(os.path.join(companies_dir, t)):
                print(f"{RED}Ошибка: папка companies/{t} не найдена{NC}")
                return 1
    else:
        tickers = get_tickers(companies_dir)

    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print(f"{CYAN}  Генерация governance.md ({date.today().isoformat()}){NC}")
    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print()
    print(f"  Компаний: {len(tickers)}")
    print()

    ok = 0
    skipped = 0
    failed = 0

    for i, ticker in enumerate(tickers, 1):
        prefix = f"  [{i}/{len(tickers)}] {ticker}"

        result = process_company(ticker, companies_dir)

        if result["skipped"]:
            print(
                f"{prefix}: {YELLOW}пропуск (нет данных — "
                f"запустите make download-events и/или make download-governance){NC}"
            )
            skipped += 1
        elif result["ok"]:
            n_div = result["n_dividends"]
            sanc = f", {RED}САНКЦИИ{NC}" if result["sanctions"] else ""
            print(f"{prefix}: {GREEN}OK{NC} — дивидендов: {n_div}{sanc}")
            ok += 1
        else:
            print(f"{prefix}: {RED}ошибка{NC}")
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
