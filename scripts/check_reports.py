#!/usr/bin/env python3
"""
Проверка выхода новых финансовых отчётов.

Скачивает квартальный CSV со smart-lab.ru и сравнивает последний
доступный период с локальным CSV в companies/{TICKER}/data/.
Если на smart-lab появился новый квартал/год — значит, компания
опубликовала отчёт.

Использование:
    python3 scripts/check_reports.py              # все компании
    python3 scripts/check_reports.py SBER LKOH    # конкретные тикеры
    python3 scripts/check_reports.py --download    # + скачать данные для новых отчётов

Автор: AlmazNurmukhametov
"""

import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import date


# Smart-Lab квартальные данные МСФО
QUARTERLY_URL = "https://smart-lab.ru/q/{ticker}/f/q/MSFO/download/"
YEARLY_URL = "https://smart-lab.ru/q/{ticker}/f/y/MSFO/download/"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DELAY_SECONDS = 1.5

# Цвета
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
NC = "\033[0m"


def fetch_csv_header(url: str) -> str | None:
    """Скачивает CSV и возвращает первую строку (заголовок с периодами)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            # Читаем только первые 4KB — достаточно для заголовка
            data = resp.read(4096)
            text = data.decode("utf-8-sig", errors="replace")
            first_line = text.split("\n")[0].strip()
            return first_line
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None


def parse_periods(header: str) -> list[str]:
    """
    Извлекает список периодов из заголовка CSV.
    Формат: ";2023Q1;2023Q2;...;2025Q3;LTM"
    Возвращает отсортированный список типа ['2024Q4', '2025Q1', '2025Q2', '2025Q3'].
    """
    parts = header.split(";")
    periods = []
    for p in parts:
        p = p.strip().strip('"')
        # Квартальные: 2024Q1, 2024Q2, ...
        if re.match(r"^\d{4}Q[1-4]$", p):
            periods.append(p)
        # Годовые: 2023, 2024, ...
        elif re.match(r"^\d{4}$", p):
            periods.append(p)
    return sorted(periods)


def get_latest_period(periods: list[str]) -> str:
    """Возвращает самый свежий период."""
    if not periods:
        return ""
    return periods[-1]


def get_local_latest_period(companies_dir: str, ticker: str, csv_type: str) -> str:
    """
    Читает заголовок локального CSV и возвращает последний период.
    csv_type: "quarterly" или "yearly"
    """
    filename = f"smartlab_{csv_type}.csv"
    csv_path = os.path.join(companies_dir, ticker, "data", filename)
    if not os.path.exists(csv_path):
        return ""
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            header = f.readline().strip()
        periods = parse_periods(header)
        return get_latest_period(periods)
    except (OSError, UnicodeDecodeError):
        return ""


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


def check_ticker(ticker: str, companies_dir: str) -> dict:
    """
    Проверяет один тикер. Сравнивает remote smart-lab с локальным CSV.
    Возвращает:
    {
        "status": "new" | "unchanged" | "error",
        "quarterly": {"local": "2025Q2", "remote": "2025Q3"},
        "yearly": {"local": "2024", "remote": "2024"},
    }
    """
    result = {"status": "unchanged", "quarterly": {}, "yearly": {}}

    # Квартальные
    q_header = fetch_csv_header(QUARTERLY_URL.format(ticker=ticker))
    if q_header:
        q_periods = parse_periods(q_header)
        q_remote = get_latest_period(q_periods)
        q_local = get_local_latest_period(companies_dir, ticker, "quarterly")

        result["quarterly"] = {
            "local": q_local,
            "remote": q_remote,
            "all_periods": q_periods[-6:] if q_periods else [],
        }

        if q_remote and q_remote != q_local:
            result["status"] = "new"
    else:
        result["quarterly"] = {"error": "не удалось загрузить"}

    time.sleep(DELAY_SECONDS)

    # Годовые
    y_header = fetch_csv_header(YEARLY_URL.format(ticker=ticker))
    if y_header:
        y_periods = parse_periods(y_header)
        y_remote = get_latest_period(y_periods)
        y_local = get_local_latest_period(companies_dir, ticker, "yearly")

        result["yearly"] = {
            "local": y_local,
            "remote": y_remote,
        }

        if y_remote and y_remote != y_local:
            result["status"] = "new"
    else:
        result["yearly"] = {"error": "не удалось загрузить"}

    time.sleep(DELAY_SECONDS)

    return result


def main():
    """Основная функция."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    companies_dir = os.path.join(base_dir, "companies")

    if not os.path.exists(companies_dir):
        print(f"{RED}Ошибка: директория {companies_dir} не найдена{NC}")
        return 1

    args = sys.argv[1:]
    do_download = "--download" in args
    args = [a for a in args if a != "--download"]

    if args:
        tickers = [t.upper() for t in args]
    else:
        tickers = get_tickers(companies_dir)

    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print(f"{CYAN}  Проверка выхода отчётов ({date.today().isoformat()}){NC}")
    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print()

    new_reports = []
    errors = 0

    for i, ticker in enumerate(tickers, 1):
        prefix = f"  [{i}/{len(tickers)}] {ticker}"
        result = check_ticker(ticker, companies_dir)

        q = result.get("quarterly", {})
        y = result.get("yearly", {})

        if result["status"] == "new":
            parts = []

            if q.get("remote") and q.get("remote") != q.get("local"):
                local_str = q["local"] or "—"
                parts.append(f"кварт: {local_str} → {BOLD}{q['remote']}{NC}{GREEN}")

            if y.get("remote") and y.get("remote") != y.get("local"):
                local_str = y["local"] or "—"
                parts.append(f"год: {local_str} → {BOLD}{y['remote']}{NC}{GREEN}")

            info = ", ".join(parts)
            print(f"{prefix}: {GREEN}НОВЫЙ ОТЧЁТ! {info}{NC}")
            new_reports.append((ticker, result))
        elif q.get("error") or y.get("error"):
            print(f"{prefix}: {RED}ошибка загрузки{NC}")
            errors += 1
        else:
            q_latest = q.get("remote", "?")
            y_latest = y.get("remote", "?")
            print(f"{prefix}: без изменений (кварт: {q_latest}, год: {y_latest})")

    # Итоги
    print()
    new_tickers = [t for t, _ in new_reports]

    if new_reports:
        print(f"{GREEN}{BOLD}Новые отчёты ({len(new_reports)}):{NC}")
        for ticker, res in new_reports:
            q = res.get("quarterly", {})
            y = res.get("yearly", {})
            parts = []
            if q.get("remote") and q.get("remote") != q.get("local", q.get("remote")):
                parts.append(f"квартальный: {q['remote']}")
            if y.get("remote") and y.get("remote") != y.get("local", y.get("remote")):
                parts.append(f"годовой: {y['remote']}")
            print(f"  {GREEN}{ticker}{NC}: {', '.join(parts)}")

        # Скачиваем данные для новых отчётов
        if do_download and new_tickers:
            print()
            print(f"{CYAN}Скачивание данных со smart-lab для {len(new_tickers)} компаний...{NC}")
            smartlab_script = os.path.join(script_dir, "download_smartlab.py")
            subprocess.run(
                [sys.executable, smartlab_script, "--force"] + new_tickers,
                cwd=base_dir,
            )

        # Записываем список тикеров в файл (для Makefile)
        new_tickers_path = os.path.join(base_dir, "reports_new_tickers.txt")
        with open(new_tickers_path, "w") as f:
            f.write("\n".join(new_tickers) + "\n")
        print()
        print(f"Тикеры с новыми отчётами: {' '.join(new_tickers)}")
        print(f"Сохранено в: reports_new_tickers.txt")
    else:
        print("Новых отчётов не обнаружено.")
        # Очищаем файл тикеров
        new_tickers_path = os.path.join(base_dir, "reports_new_tickers.txt")
        with open(new_tickers_path, "w") as f:
            f.write("")

    if errors:
        print(f"{YELLOW}{errors} компаний с ошибками загрузки{NC}")

    return 0


if __name__ == "__main__":
    exit(main())
