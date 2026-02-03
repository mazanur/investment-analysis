#!/usr/bin/env python3
"""
Загрузка финансовых данных со smart-lab.ru.

Скачивает годовые и квартальные МСФО в CSV для каждой компании.
Сохраняет в companies/{TICKER}/data/smartlab_yearly.csv и smartlab_quarterly.csv.

Использование:
    python3 scripts/download_smartlab.py              # все компании
    python3 scripts/download_smartlab.py SBER LKOH    # конкретные тикеры
    python3 scripts/download_smartlab.py --force       # перезаписать существующие

Автор: AlmazNurmukhametov
"""

import os
import sys
import time
import urllib.request
import urllib.error
from datetime import date


# Настройки
DELAY_SECONDS = 1.5  # Задержка между запросами (вежливость к серверу)
YEARLY_URL = "https://smart-lab.ru/q/{ticker}/f/y/MSFO/download/"
QUARTERLY_URL = "https://smart-lab.ru/q/{ticker}/f/q/MSFO/download/"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Цвета для вывода
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
NC = "\033[0m"


def download_csv(url: str) -> bytes | None:
    """Скачивает CSV по URL. Возвращает bytes или None при ошибке."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            # Проверяем что это CSV, а не HTML-страница с ошибкой
            if data[:5] == b"<html" or data[:5] == b"<!DOC":
                return None
            # Проверяем что есть содержимое (минимум заголовок)
            if len(data) < 50:
                return None
            return data
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        print(f"    {RED}Ошибка загрузки {url}: {e}{NC}")
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
        # Проверяем что не делистингован
        index_file = os.path.join(path, "_index.md")
        if os.path.exists(index_file):
            with open(index_file, "r", encoding="utf-8") as f:
                content = f.read(500)  # Читаем только начало
                if "status: delisted" in content or "delisted: true" in content:
                    continue
        tickers.append(name)
    return tickers


def download_company(ticker: str, companies_dir: str, force: bool = False) -> dict:
    """
    Скачивает CSV для одной компании.

    Возвращает dict с результатами:
        {"yearly": True/False, "quarterly": True/False, "skipped": True/False}
    """
    data_dir = os.path.join(companies_dir, ticker, "data")
    os.makedirs(data_dir, exist_ok=True)

    yearly_path = os.path.join(data_dir, "smartlab_yearly.csv")
    quarterly_path = os.path.join(data_dir, "smartlab_quarterly.csv")

    result = {"yearly": False, "quarterly": False, "skipped": False}

    # Пропускаем если файлы уже есть и обновлены сегодня (без --force)
    if not force:
        today = date.today().isoformat()
        yearly_fresh = (
            os.path.exists(yearly_path)
            and date.fromtimestamp(os.path.getmtime(yearly_path)).isoformat() == today
        )
        quarterly_fresh = (
            os.path.exists(quarterly_path)
            and date.fromtimestamp(os.path.getmtime(quarterly_path)).isoformat()
            == today
        )
        if yearly_fresh and quarterly_fresh:
            result["skipped"] = True
            return result

    # Скачиваем годовые
    yearly_data = download_csv(YEARLY_URL.format(ticker=ticker))
    if yearly_data:
        with open(yearly_path, "wb") as f:
            f.write(yearly_data)
        result["yearly"] = True
    time.sleep(DELAY_SECONDS)

    # Скачиваем квартальные
    quarterly_data = download_csv(QUARTERLY_URL.format(ticker=ticker))
    if quarterly_data:
        with open(quarterly_path, "wb") as f:
            f.write(quarterly_data)
        result["quarterly"] = True
    time.sleep(DELAY_SECONDS)

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

    # Определяем список тикеров
    if args:
        tickers = [t.upper() for t in args]
        # Проверяем что папки существуют
        for t in tickers:
            if not os.path.isdir(os.path.join(companies_dir, t)):
                print(f"{RED}Ошибка: папка companies/{t} не найдена{NC}")
                return 1
    else:
        tickers = get_tickers(companies_dir)

    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print(f"{CYAN}  Загрузка данных со smart-lab ({date.today().isoformat()}){NC}")
    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print()
    print(f"  Компаний: {len(tickers)}")
    print(f"  Задержка: {DELAY_SECONDS} сек между запросами")
    if force:
        print(f"  {YELLOW}Режим --force: перезаписываем существующие файлы{NC}")
    print()

    ok = 0
    partial = 0
    skipped = 0
    failed = 0

    for i, ticker in enumerate(tickers, 1):
        prefix = f"  [{i}/{len(tickers)}] {ticker}"

        result = download_company(ticker, companies_dir, force=force)

        if result["skipped"]:
            print(f"{prefix}: {YELLOW}пропуск (уже обновлено сегодня){NC}")
            skipped += 1
        elif result["yearly"] and result["quarterly"]:
            print(f"{prefix}: {GREEN}OK (годовые + квартальные){NC}")
            ok += 1
        elif result["yearly"] or result["quarterly"]:
            parts = []
            if result["yearly"]:
                parts.append("годовые")
            if result["quarterly"]:
                parts.append("квартальные")
            print(f"{prefix}: {YELLOW}частично ({', '.join(parts)}){NC}")
            partial += 1
        else:
            print(f"{prefix}: {RED}нет данных на smart-lab{NC}")
            failed += 1

    print()
    print(f"Готово: {GREEN}{ok} OK{NC}, {YELLOW}{partial} частично{NC}, "
          f"{YELLOW}{skipped} пропущено{NC}, {RED}{failed} без данных{NC}")

    return 0


if __name__ == "__main__":
    exit(main())