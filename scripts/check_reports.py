#!/usr/bin/env python3
"""
Проверка выхода новых финансовых отчётов.

Скачивает квартальный CSV со smart-lab.ru и сравнивает последний
доступный период с сохранённым состоянием. Если появился новый
квартал — значит, компания опубликовала отчёт.

Использование:
    python3 scripts/check_reports.py              # все компании
    python3 scripts/check_reports.py SBER LKOH    # конкретные тикеры
    python3 scripts/check_reports.py --download    # + скачать данные для новых отчётов

Автор: AlmazNurmukhametov
"""

import json
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

# Файл состояния — хранит последние известные периоды
STATE_FILE = "reports_state.json"

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


def get_report_date(url: str) -> str:
    """Извлекает дату последнего отчёта из строки 'Дата отчета' CSV."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read(8192)
            text = data.decode("utf-8-sig", errors="replace")
            lines = text.split("\n")
            if len(lines) >= 2:
                # Вторая строка — "Дата отчета";...;28.08.2025;...
                parts = lines[1].split(";")
                # Берём последнюю непустую дату
                dates = [p.strip().strip('"') for p in parts if re.match(r"\d{2}\.\d{2}\.\d{4}", p.strip().strip('"'))]
                if dates:
                    return dates[-1]
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        pass
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


def load_state(state_path: str) -> dict:
    """Загружает состояние из JSON."""
    if os.path.exists(state_path):
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state_path: str, state: dict):
    """Сохраняет состояние в JSON."""
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def check_ticker(ticker: str, state: dict) -> dict:
    """
    Проверяет один тикер. Возвращает:
    {
        "status": "new" | "unchanged" | "error",
        "quarterly": {"old": "2025Q2", "new": "2025Q3", "report_date": "28.08.2025"},
        "yearly": {"old": "2024", "new": "2024"},
    }
    """
    result = {"status": "unchanged", "quarterly": {}, "yearly": {}}

    # Квартальные
    q_header = fetch_csv_header(QUARTERLY_URL.format(ticker=ticker))
    if q_header:
        q_periods = parse_periods(q_header)
        q_latest = get_latest_period(q_periods)
        q_old = state.get(f"{ticker}_quarterly", "")

        result["quarterly"] = {
            "old": q_old,
            "new": q_latest,
            "all_periods": q_periods[-6:] if q_periods else [],
        }

        if q_latest and q_latest != q_old:
            result["status"] = "new"
    else:
        result["quarterly"] = {"error": "не удалось загрузить"}

    time.sleep(DELAY_SECONDS)

    # Годовые
    y_header = fetch_csv_header(YEARLY_URL.format(ticker=ticker))
    if y_header:
        y_periods = parse_periods(y_header)
        y_latest = get_latest_period(y_periods)
        y_old = state.get(f"{ticker}_yearly", "")

        result["yearly"] = {
            "old": y_old,
            "new": y_latest,
        }

        if y_latest and y_latest != y_old:
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
    state_path = os.path.join(base_dir, STATE_FILE)

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

    state = load_state(state_path)

    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print(f"{CYAN}  Проверка выхода отчётов ({date.today().isoformat()}){NC}")
    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print()

    new_reports = []
    errors = 0

    for i, ticker in enumerate(tickers, 1):
        prefix = f"  [{i}/{len(tickers)}] {ticker}"
        result = check_ticker(ticker, state)

        q = result.get("quarterly", {})
        y = result.get("yearly", {})

        if result["status"] == "new":
            parts = []

            if q.get("new") and q.get("new") != q.get("old"):
                old_str = q["old"] or "—"
                parts.append(f"кварт: {old_str} → {BOLD}{q['new']}{NC}{GREEN}")
                state[f"{ticker}_quarterly"] = q["new"]

            if y.get("new") and y.get("new") != y.get("old"):
                old_str = y["old"] or "—"
                parts.append(f"год: {old_str} → {BOLD}{y['new']}{NC}{GREEN}")
                state[f"{ticker}_yearly"] = y["new"]

            info = ", ".join(parts)
            print(f"{prefix}: {GREEN}НОВЫЙ ОТЧЁТ! {info}{NC}")
            new_reports.append((ticker, result))
        elif q.get("error") or y.get("error"):
            print(f"{prefix}: {RED}ошибка загрузки{NC}")
            errors += 1
        else:
            q_latest = q.get("new", "?")
            y_latest = y.get("new", "?")
            print(f"{prefix}: без изменений (кварт: {q_latest}, год: {y_latest})")

            # Сохраняем текущее состояние даже при первом запуске
            if q.get("new"):
                state[f"{ticker}_quarterly"] = q["new"]
            if y.get("new"):
                state[f"{ticker}_yearly"] = y["new"]

    save_state(state_path, state)

    # Итоги
    print()
    new_tickers = [t for t, _ in new_reports]

    if new_reports:
        print(f"{GREEN}{BOLD}Новые отчёты ({len(new_reports)}):{NC}")
        for ticker, res in new_reports:
            q = res.get("quarterly", {})
            y = res.get("yearly", {})
            parts = []
            if q.get("new") and q.get("new") != q.get("old", q.get("new")):
                parts.append(f"квартальный: {q['new']}")
            if y.get("new") and y.get("new") != y.get("old", y.get("new")):
                parts.append(f"годовой: {y['new']}")
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