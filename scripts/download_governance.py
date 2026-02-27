#!/usr/bin/env python3
"""
Загрузка данных для governance.md: санкционный скрининг (OpenSanctions API).

Дивиденды и финансы уже скачиваются существующими скриптами
(download_moex_events.py, download_smartlab.py).

Сохраняет в companies/{TICKER}/data/sanctions.json.

OpenSanctions API — бесплатный для некоммерческого использования.

Использование:
    python3 scripts/download_governance.py              # все компании
    python3 scripts/download_governance.py SBER LKOH    # конкретные тикеры
    python3 scripts/download_governance.py --force       # перезаписать существующие

Автор: AlmazNurmukhametov
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date


# Настройки
DELAY_SECONDS = 1.0  # OpenSanctions просит не спамить
USER_AGENT = "investment-analysis/1.0 (non-commercial research)"
SEARCH_LIMIT = 10
RELEVANCE_THRESHOLD = 0.7  # минимальный score для релевантного совпадения

# OpenSanctions API
OPENSANCTIONS_SEARCH_URL = (
    "https://api.opensanctions.org/search/default"
    "?q={query}&limit={limit}"
)

# Цвета для вывода
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
NC = "\033[0m"


def get_api_key() -> str:
    """Читает API-ключ OpenSanctions из переменной окружения."""
    return os.environ.get("OPENSANCTIONS_API_KEY", "")


def fetch_json(url: str, api_key: str = "") -> dict | list | None:
    """Загружает JSON по URL. Возвращает parsed JSON или None."""
    headers = {"User-Agent": USER_AGENT}
    if api_key:
        headers["Authorization"] = f"ApiKey {api_key}"
    req = urllib.request.Request(url, headers=headers)
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


def get_company_name(ticker: str, companies_dir: str) -> str:
    """
    Получает имя компании для поиска в OpenSanctions.

    Приоритет: _index.md (name) → moex_market.json (shortname) → ticker.
    """
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

    return ticker


def search_sanctions(query: str, api_key: str = "") -> dict | None:
    """Ищет компанию в OpenSanctions."""
    encoded_query = urllib.parse.quote(query)
    url = OPENSANCTIONS_SEARCH_URL.format(query=encoded_query, limit=SEARCH_LIMIT)
    return fetch_json(url, api_key=api_key)


def download_company(
    ticker: str,
    companies_dir: str,
    api_key: str = "",
    force: bool = False,
) -> dict:
    """
    Скачивает данные о санкциях для одной компании.

    Возвращает dict с результатами:
        {"ok": True/False, "skipped": True/False, "data": dict}
    """
    data_dir = os.path.join(companies_dir, ticker, "data")
    os.makedirs(data_dir, exist_ok=True)

    output_path = os.path.join(data_dir, "sanctions.json")
    result = {"ok": False, "skipped": False, "data": None}

    # Пропускаем если файл уже обновлён сегодня
    if not force and os.path.exists(output_path):
        today = date.today().isoformat()
        file_date = date.fromtimestamp(os.path.getmtime(output_path)).isoformat()
        if file_date == today:
            result["skipped"] = True
            return result

    company_name = get_company_name(ticker, companies_dir)

    # Поиск в OpenSanctions
    raw_response = search_sanctions(company_name, api_key=api_key)
    time.sleep(DELAY_SECONDS)

    if raw_response is None:
        return result

    # Парсим результаты
    results = []
    for r in raw_response.get("results", []):
        results.append({
            "id": r.get("id", ""),
            "caption": r.get("caption", ""),
            "schema": r.get("schema", ""),
            "datasets": list(r.get("datasets", [])),
            "score": r.get("score", 0),
        })

    # Релевантные совпадения
    relevant = [r for r in results if r["score"] > RELEVANCE_THRESHOLD]

    sanctions_data = {
        "ticker": ticker,
        "company_name": company_name,
        "query": company_name,
        "date": date.today().isoformat(),
        "results": results,
        "total": raw_response.get("total", {}).get("value", 0),
        "relevant_matches": len(relevant),
    }

    # Сохраняем
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sanctions_data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    result["ok"] = True
    result["data"] = sanctions_data
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

    # Проверяем API-ключ
    api_key = get_api_key()

    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print(f"{CYAN}  Санкционный скрининг — OpenSanctions ({date.today().isoformat()}){NC}")
    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print()

    if not api_key:
        print(f"  {YELLOW}OPENSANCTIONS_API_KEY не задан.{NC}")
        print(f"  Получите бесплатный ключ: https://www.opensanctions.org/api/")
        print(f"  Использование: OPENSANCTIONS_API_KEY=ваш_ключ make download-governance")
        print()
        return 0

    print(f"  Компаний: {len(tickers)}")
    if force:
        print(f"  {YELLOW}Режим --force: перезаписываем существующие{NC}")
    print()

    ok = 0
    skipped = 0
    failed = 0

    for i, ticker in enumerate(tickers, 1):
        prefix = f"  [{i}/{len(tickers)}] {ticker}"

        result = download_company(ticker, companies_dir, api_key=api_key, force=force)

        if result["skipped"]:
            print(f"{prefix}: {YELLOW}пропуск (уже обновлено сегодня){NC}")
            skipped += 1
        elif result["ok"]:
            d = result["data"]
            n = d["relevant_matches"]
            total = d["total"]
            if n > 0:
                print(f"{prefix}: {RED}НАЙДЕНО {n} совпадений{NC} (из {total})")
            else:
                print(f"{prefix}: {GREEN}OK{NC} — совпадений нет (проверено {total})")
            ok += 1
        else:
            print(f"{prefix}: {RED}ошибка API{NC}")
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
