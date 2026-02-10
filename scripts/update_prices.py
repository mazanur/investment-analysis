#!/usr/bin/env python3
"""
Обновление цен акций с MOEX ISS API и ведение истории.

Для каждого тикера:
  1. Забирает текущую цену с MOEX (batch-запрос — все тикеры за 1-2 вызова)
  2. Дописывает строку в companies/{TICKER}/data/price_history.csv
  3. Обновляет current_price в companies/{TICKER}/_index.md

Запускать в конце торгового дня (после 18:50 МСК).

Использование:
    python3 scripts/update_prices.py              # все компании
    python3 scripts/update_prices.py SBER LKOH    # конкретные тикеры
    python3 scripts/update_prices.py --force       # перезаписать запись за сегодня
    python3 scripts/update_prices.py --backfill    # загрузить историю за 365 дней
    python3 scripts/update_prices.py --backfill 90 # загрузить историю за 90 дней

Автор: AlmazNurmukhametov
"""

import csv
import io
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import date, timedelta


# MOEX ISS API — все бумаги на TQBR одним запросом
# Пагинация: API возвращает до 100 строк, start= для следующей страницы
TQBR_URL = (
    "https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR"
    "/securities.json?iss.meta=off&iss.json=extended&start={start}"
)

CANDLES_URL = (
    "https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR"
    "/securities/{ticker}/candles.json"
    "?iss.meta=off&iss.json=extended&interval=24"
    "&from={date_from}&till={date_till}"
)

DELAY_SECONDS = 0.5

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

CSV_HEADER = ["date", "close", "open", "high", "low", "volume_rub", "market_cap_bln"]

# Цвета
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
NC = "\033[0m"


def fetch_json(url: str, retries: int = 3) -> list | dict | None:
    """Загружает JSON по URL с повторами при ошибке."""
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            if attempt < retries:
                print(f"  {YELLOW}Попытка {attempt}/{retries} не удалась: {e}, повтор через {attempt * 2}с...{NC}")
                time.sleep(attempt * 2)
            else:
                print(f"  {RED}Ошибка загрузки ({retries} попыток): {e}{NC}")
                return None


def fetch_all_tqbr() -> dict[str, dict]:
    """
    Загружает все бумаги с доски TQBR.
    Возвращает dict: ticker -> {last, open, high, low, valtoday, issuecap, ...}
    """
    all_securities = {}
    start = 0

    while True:
        data = fetch_json(TQBR_URL.format(start=start))
        if not data or not isinstance(data, list):
            break

        page_count = 0
        for block in data:
            if not isinstance(block, dict):
                continue

            # Собираем статические данные (securities block)
            securities = block.get("securities")
            if securities and isinstance(securities, list):
                for row in securities:
                    if not isinstance(row, dict):
                        continue
                    ticker = row.get("SECID", "")
                    if ticker:
                        all_securities.setdefault(ticker, {})
                        all_securities[ticker]["issuesize"] = row.get("ISSUESIZE", 0)
                        page_count += 1

            # Собираем торговые данные (marketdata block)
            marketdata = block.get("marketdata")
            if marketdata and isinstance(marketdata, list):
                for row in marketdata:
                    if not isinstance(row, dict):
                        continue
                    ticker = row.get("SECID", "")
                    if ticker:
                        all_securities.setdefault(ticker, {})
                        all_securities[ticker].update({
                            "last": row.get("LAST") or row.get("LCLOSEPRICE", 0),
                            "open": row.get("OPEN", 0),
                            "high": row.get("HIGH", 0),
                            "low": row.get("LOW", 0),
                            "valtoday": row.get("VALTODAY", 0),
                            "issuecap": row.get("ISSUECAPITALIZATION", 0),
                        })

        # Если страница пустая — конец
        if page_count == 0:
            break

        start += 100  # Следующая страница

    return all_securities


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


def append_to_csv(csv_path: str, row: dict, force: bool = False) -> bool:
    """
    Дописывает строку в CSV. Если запись за сегодня уже есть — пропускает
    (или перезаписывает при force=True).
    Возвращает True если записано, False если пропущено.
    """
    today = date.today().isoformat()
    existing_rows = []
    has_today = False

    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if r.get("date") == today:
                    has_today = True
                    if force:
                        continue  # Пропускаем старую запись за сегодня
                existing_rows.append(r)

    if has_today and not force:
        return False

    # Дописываем новую строку
    new_row = {col: row.get(col, "") for col in CSV_HEADER}
    existing_rows.append(new_row)

    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(existing_rows)

    return True


def update_current_price(index_path: str, new_price: float) -> bool:
    """Обновляет current_price в YAML-frontmatter _index.md."""
    if not os.path.exists(index_path):
        return False

    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Ищем current_price в YAML-блоке (между ---)
    pattern = r"(current_price:\s*)\S+"
    match = re.search(pattern, content)
    if not match:
        return False

    # Форматируем цену: целое если без копеек, иначе с десятичными
    if new_price == int(new_price):
        price_str = str(int(new_price))
    else:
        price_str = f"{new_price:.2f}".rstrip("0").rstrip(".")

    new_content = re.sub(pattern, f"current_price: {price_str}", content, count=1)

    if new_content == content:
        return False

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return True


def fetch_candles(ticker: str, date_from: str, date_till: str) -> list[dict]:
    """Загружает дневные свечи с MOEX ISS. Возвращает список {date, close, open, high, low, value}."""
    candles = []
    url = CANDLES_URL.format(ticker=ticker, date_from=date_from, date_till=date_till)
    data = fetch_json(url)
    if not data or not isinstance(data, list):
        return candles

    for block in data:
        if not isinstance(block, dict):
            continue
        candles_block = block.get("candles")
        if candles_block and isinstance(candles_block, list):
            for row in candles_block:
                if isinstance(row, dict) and row.get("close"):
                    candles.append({
                        "date": row.get("begin", "")[:10],
                        "close": row.get("close", 0),
                        "open": row.get("open", 0),
                        "high": row.get("high", 0),
                        "low": row.get("low", 0),
                        "volume_rub": int(row.get("value", 0)),
                    })

    return candles


def backfill_ticker(ticker: str, companies_dir: str, days: int) -> int:
    """
    Загружает историю свечей за N дней и записывает в price_history.csv.
    Возвращает количество записанных строк.
    """
    date_till = date.today().isoformat()
    date_from = (date.today() - timedelta(days=days)).isoformat()

    # MOEX ISS может вернуть максимум ~500 свечей за запрос,
    # для >500 дней нужно разбить на части
    all_candles = []
    chunk_from = date_from
    while chunk_from < date_till:
        chunk_till_date = min(
            date.fromisoformat(chunk_from) + timedelta(days=499),
            date.today()
        )
        chunk_till = chunk_till_date.isoformat()

        candles = fetch_candles(ticker, chunk_from, chunk_till)
        all_candles.extend(candles)
        time.sleep(DELAY_SECONDS)

        if chunk_till >= date_till:
            break
        chunk_from = (chunk_till_date + timedelta(days=1)).isoformat()

    if not all_candles:
        return 0

    # Читаем существующий CSV (если есть) для слияния
    csv_path = os.path.join(companies_dir, ticker, "data", "price_history.csv")
    existing = {}
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                existing[r.get("date", "")] = r

    # Добавляем свечи (не перезаписываем существующие даты)
    for candle in all_candles:
        d = candle["date"]
        if d not in existing:
            existing[d] = {
                "date": d,
                "close": candle["close"],
                "open": candle["open"],
                "high": candle["high"],
                "low": candle["low"],
                "volume_rub": candle["volume_rub"],
                "market_cap_bln": "",  # нет данных в свечах
            }

    # Сортируем по дате и записываем
    sorted_rows = sorted(existing.values(), key=lambda r: r.get("date", ""))

    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(sorted_rows)

    return len(sorted_rows)


def run_backfill(tickers: list[str], companies_dir: str, days: int):
    """Запускает backfill для списка тикеров."""
    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print(f"{CYAN}  Backfill: загрузка истории за {days} дней{NC}")
    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print()

    ok = 0
    failed = 0

    for i, ticker in enumerate(tickers, 1):
        prefix = f"  [{i}/{len(tickers)}] {ticker}"
        count = backfill_ticker(ticker, companies_dir, days)
        if count > 0:
            print(f"{prefix}: {GREEN}{count} записей{NC}")
            ok += 1
        else:
            print(f"{prefix}: {RED}нет данных{NC}")
            failed += 1

    print()
    print(f"Готово: {GREEN}{ok} OK{NC}, {RED}{failed} без данных{NC}")


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

    # --backfill [days]
    backfill_days = 0
    if "--backfill" in args:
        idx = args.index("--backfill")
        args.pop(idx)
        # Следующий аргумент — кол-во дней (если число)
        if idx < len(args) and args[idx].isdigit():
            backfill_days = int(args.pop(idx))
        else:
            backfill_days = 365

    if args:
        tickers = [t.upper() for t in args]
        for t in tickers:
            if not os.path.isdir(os.path.join(companies_dir, t)):
                print(f"{RED}Ошибка: папка companies/{t} не найдена{NC}")
                return 1
    else:
        tickers = get_tickers(companies_dir)

    # Режим backfill — загрузка исторических свечей
    if backfill_days > 0:
        run_backfill(tickers, companies_dir, backfill_days)
        return 0

    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print(f"{CYAN}  Обновление цен с MOEX ({date.today().isoformat()}){NC}")
    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print()

    # Batch-загрузка всех бумаг TQBR
    print(f"  Загрузка данных с MOEX ISS...", end=" ", flush=True)
    moex_data = fetch_all_tqbr()
    print(f"{GREEN}{len(moex_data)} бумаг загружено{NC}")
    print()

    if not moex_data:
        print(f"{RED}Не удалось загрузить данные с MOEX{NC}")
        return 1

    updated = 0
    skipped = 0
    not_found = 0
    price_changes = []

    for ticker in tickers:
        md = moex_data.get(ticker)
        if not md or not md.get("last"):
            print(f"  {ticker}: {YELLOW}нет данных на MOEX{NC}")
            not_found += 1
            continue

        price = md["last"]
        market_cap_bln = round(md.get("issuecap", 0) / 1_000_000_000, 1)

        # Читаем предыдущую цену из _index.md
        index_path = os.path.join(companies_dir, ticker, "_index.md")
        old_price = None
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                for line in f:
                    m = re.match(r"current_price:\s*(\S+)", line)
                    if m:
                        try:
                            old_price = float(m.group(1))
                        except ValueError:
                            pass
                        break

        # Дописываем в CSV
        csv_path = os.path.join(companies_dir, ticker, "data", "price_history.csv")
        row = {
            "date": date.today().isoformat(),
            "close": price,
            "open": md.get("open", 0),
            "high": md.get("high", 0),
            "low": md.get("low", 0),
            "volume_rub": int(md.get("valtoday", 0)),
            "market_cap_bln": market_cap_bln,
        }

        written = append_to_csv(csv_path, row, force=force)

        # Обновляем current_price в _index.md
        price_updated = update_current_price(index_path, price)

        if not written and not price_updated:
            print(f"  {ticker}: {YELLOW}пропуск (уже обновлено){NC}")
            skipped += 1
            continue

        # Считаем изменение
        change_str = ""
        if old_price and old_price > 0:
            change_pct = (price - old_price) / old_price * 100
            if change_pct > 0:
                change_str = f" {GREEN}+{change_pct:.1f}%{NC}"
            elif change_pct < 0:
                change_str = f" {RED}{change_pct:.1f}%{NC}"
            price_changes.append((ticker, old_price, price, change_pct))

        print(f"  {ticker}: {GREEN}{price}{NC}{change_str}")
        updated += 1

    # Итоги
    print()
    print(
        f"Готово: {GREEN}{updated} обновлено{NC}, "
        f"{YELLOW}{skipped} пропущено{NC}, "
        f"{RED}{not_found} без данных{NC}"
    )

    # Топ изменений
    if price_changes:
        print()
        print(f"{CYAN}Топ изменений:{NC}")
        sorted_changes = sorted(price_changes, key=lambda x: abs(x[3]), reverse=True)
        for ticker, old_p, new_p, pct in sorted_changes[:10]:
            color = GREEN if pct > 0 else RED
            print(f"  {ticker}: {old_p} -> {new_p} ({color}{pct:+.1f}%{NC})")

    return 0


if __name__ == "__main__":
    exit(main())
