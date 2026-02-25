#!/usr/bin/env python3
"""
Генератор catalysts.json для компаний.

Агрегирует катализаторы из нескольких источников:
- _index.md — key_risks (негативные), key_opportunities (позитивные)
- russia/macro.md — даты заседаний ЦБ (макро-катализаторы)

Использование:
    python3 scripts/generate_catalysts.py              # все компании
    python3 scripts/generate_catalysts.py SBER LKOH    # конкретные тикеры

Автор: AlmazNurmukhametov
"""

import json
import os
import re
import sys
from datetime import date


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

# Ключевые слова для magnitude=high
HIGH_MAGNITUDE_KEYWORDS = [
    "санкц", "ставк", "ЦБ", "дивиденд", "SDN", "OFAC",
    "делистинг", "национализ", "IPO", "SPO", "buyback",
]


def parse_yaml_frontmatter_with_lists(content: str) -> dict:
    """
    Парсит YAML frontmatter с поддержкой list-значений.

    Возвращает dict, где list-ключи (key_risks, key_opportunities)
    содержат list[str], а простые ключи — str.
    """
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    yaml_content = match.group(1)
    result = {}
    current_list_key = None

    for line in yaml_content.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            current_list_key = None
            continue

        # Элемент списка: "  - value"
        list_match = re.match(r"^\s+-\s+(.+)$", line)
        if list_match and current_list_key:
            result[current_list_key].append(list_match.group(1).strip())
            continue

        # Пара key: value
        kv_match = re.match(r"^([a-zA-Z][a-zA-Z0-9_-]*):\s*(.*)$", stripped)
        if kv_match:
            key = kv_match.group(1)
            value = kv_match.group(2).strip()

            # Убираем кавычки
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]

            if not value:
                # Пустое значение → начало списка
                result[key] = []
                current_list_key = key
            else:
                result[key] = value
                current_list_key = None
        else:
            current_list_key = None

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
                meta = parse_yaml_frontmatter_with_lists(content)
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


def classify_magnitude(text: str) -> str:
    """Эвристическая классификация magnitude по тексту."""
    text_lower = text.lower()
    for kw in HIGH_MAGNITUDE_KEYWORDS:
        if kw.lower() in text_lower:
            return "high"
    return "medium"


def extract_index_catalysts(index_file: str) -> list[dict]:
    """Извлекает катализаторы из key_risks и key_opportunities в _index.md."""
    if not os.path.exists(index_file):
        return []

    try:
        with open(index_file, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return []

    meta = parse_yaml_frontmatter_with_lists(content)
    catalysts = []

    # key_opportunities → positive
    for item in meta.get("key_opportunities", []):
        if isinstance(item, str) and item.strip():
            catalysts.append({
                "type": "opportunity",
                "impact": "positive",
                "magnitude": classify_magnitude(item),
                "date": None,
                "description": item.strip(),
                "source": "index",
            })

    # key_risks → negative
    for item in meta.get("key_risks", []):
        if isinstance(item, str) and item.strip():
            catalysts.append({
                "type": "risk",
                "impact": "negative",
                "magnitude": classify_magnitude(item),
                "date": None,
                "description": item.strip(),
                "source": "index",
            })

    return catalysts


def build_cb_catalysts(cb_meetings: list[str]) -> list[dict]:
    """Формирует катализаторы из дат заседаний ЦБ."""
    return [
        {
            "type": "cb_meeting",
            "impact": "mixed",
            "magnitude": "high",
            "date": cb_date,
            "description": "Заседание ЦБ по ключевой ставке",
            "source": "macro",
        }
        for cb_date in cb_meetings
    ]


def build_summary(catalysts: list[dict]) -> dict:
    """Формирует summary-статистику."""
    positive = sum(1 for c in catalysts if c["impact"] == "positive")
    negative = sum(1 for c in catalysts if c["impact"] == "negative")
    mixed = sum(1 for c in catalysts if c["impact"] == "mixed")

    return {
        "total": len(catalysts),
        "positive": positive,
        "negative": negative,
        "mixed": mixed,
    }


def process_company(
    ticker: str,
    companies_dir: str,
    cb_catalysts: list[dict],
) -> dict | None:
    """
    Генерирует данные catalysts.json для одной компании.

    Возвращает dict для записи или None если нет данных.
    """
    index_file = os.path.join(companies_dir, ticker, "_index.md")
    if not os.path.exists(index_file):
        return None

    company_name = read_company_name(ticker, companies_dir)

    # Собираем катализаторы из _index.md
    catalysts = extract_index_catalysts(index_file)

    # Добавляем заседания ЦБ
    catalysts.extend(cb_catalysts)

    if not catalysts:
        return None

    return {
        "ticker": ticker,
        "company_name": company_name,
        "generated": date.today().isoformat(),
        "catalysts": catalysts,
        "summary": build_summary(catalysts),
    }


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
    print(f"{CYAN}  Генерация catalysts.json ({date.today().isoformat()}){NC}")
    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print()
    print(f"  Компаний: {len(tickers)}")

    # Загружаем даты заседаний ЦБ (один раз для всех)
    cb_meetings = read_cb_meetings(base_dir)
    cb_catalysts = build_cb_catalysts(cb_meetings)
    if cb_meetings:
        print(f"  Заседания ЦБ: {len(cb_meetings)} предстоящих")
    print()

    ok = 0
    skipped = 0

    for i, ticker in enumerate(tickers, 1):
        prefix = f"  [{i}/{len(tickers)}] {ticker}"

        result = process_company(ticker, companies_dir, cb_catalysts)

        if result is None:
            print(f"{prefix}: {YELLOW}пропуск (нет _index.md или key_risks/key_opportunities){NC}")
            skipped += 1
            continue

        # Записываем файл
        data_dir = os.path.join(companies_dir, ticker, "data")
        os.makedirs(data_dir, exist_ok=True)

        output_file = os.path.join(data_dir, "catalysts.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write("\n")

        summary = result["summary"]
        print(
            f"{prefix}: {GREEN}OK{NC} — "
            f"+{summary['positive']} / -{summary['negative']} / "
            f"~{summary['mixed']} (всего {summary['total']})"
        )
        ok += 1

    print()
    print(
        f"Готово: {GREEN}{ok} OK{NC}, "
        f"{YELLOW}{skipped} пропущено{NC}"
    )

    return 0


if __name__ == "__main__":
    exit(main())