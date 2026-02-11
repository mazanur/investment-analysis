#!/usr/bin/env python3
"""
Загрузка рыночных данных с MOEX ISS API.

Скачивает текущую цену, объём, капитализацию, рассчитывает ADV и спред.
Сохраняет в companies/{TICKER}/data/moex_market.json.

MOEX ISS API — публичный, не требует авторизации.

Использование:
    python3 scripts/download_moex.py              # все компании
    python3 scripts/download_moex.py SBER LKOH    # конкретные тикеры
    python3 scripts/download_moex.py --force       # перезаписать существующие

Автор: AlmazNurmukhametov
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import date, timedelta


# Настройки
DELAY_SECONDS = 0.5  # MOEX API быстрый, можно меньше задержки
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# MOEX ISS API endpoints
SECURITIES_URL = (
    "http://iss.moex.com/iss/engines/stock/markets/shares/boardgroups/57"
    "/securities/{ticker}.json?iss.meta=off&iss.json=extended&lang=ru"
)
CANDLES_URL = (
    "http://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR"
    "/securities/{ticker}/candles.json"
    "?iss.meta=off&iss.json=extended&interval=24"
    "&from={date_from}&till={date_till}&lang=ru"
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


def parse_securities_data(data: list) -> dict | None:
    """
    Парсит ответ securities endpoint.
    ISS extended JSON format: массив объектов с полями-ключами.
    """
    if not data or not isinstance(data, list):
        return None

    result = {}

    for block in data:
        if not isinstance(block, dict):
            continue

        # Securities block содержит статические данные
        securities = block.get("securities")
        if securities and isinstance(securities, list):
            for row in securities:
                if isinstance(row, dict) and row.get("BOARDID") == "TQBR":
                    result["board"] = "TQBR"
                    result["shortname"] = row.get("SHORTNAME", "")
                    result["secname"] = row.get("SECNAME", "")
                    result["lotsize"] = row.get("LOTSIZE", 0)
                    result["issuesize"] = row.get("ISSUESIZE", 0)
                    result["prevprice"] = row.get("PREVPRICE", 0)
                    result["listlevel"] = row.get("LISTLEVEL", 0)
                    break

        # Marketdata block содержит текущие торговые данные
        marketdata = block.get("marketdata")
        if marketdata and isinstance(marketdata, list):
            for row in marketdata:
                if isinstance(row, dict) and row.get("BOARDID") == "TQBR":
                    result["last"] = row.get("LAST") or row.get("LCLOSEPRICE", 0)
                    result["bid"] = row.get("BID", 0)
                    result["offer"] = row.get("OFFER", 0)
                    result["open"] = row.get("OPEN", 0)
                    result["high"] = row.get("HIGH", 0)
                    result["low"] = row.get("LOW", 0)
                    result["waprice"] = row.get("WAPRICE", 0)
                    result["voltoday"] = row.get("VOLTODAY", 0)
                    result["valtoday"] = row.get("VALTODAY", 0)
                    result["numtrades"] = row.get("NUMTRADES", 0)
                    result["issuecap"] = row.get("ISSUECAPITALIZATION", 0)
                    result["updatetime"] = row.get("UPDATETIME", "")
                    break

    return result if result else None


def parse_candles_data(data: list) -> list[dict]:
    """Парсит ответ candles endpoint. Возвращает список дневных свечей."""
    candles = []

    if not data or not isinstance(data, list):
        return candles

    for block in data:
        if not isinstance(block, dict):
            continue

        candles_block = block.get("candles")
        if candles_block and isinstance(candles_block, list):
            for row in candles_block:
                if isinstance(row, dict):
                    candles.append(
                        {
                            "date": row.get("begin", "")[:10],
                            "open": row.get("open", 0),
                            "close": row.get("close", 0),
                            "high": row.get("high", 0),
                            "low": row.get("low", 0),
                            "volume": row.get("volume", 0),
                            "value": row.get("value", 0),
                        }
                    )

    return candles


def calculate_adv(candles: list[dict], days: int = 30) -> float:
    """Рассчитывает ADV (Average Daily Value) за последние N торговых дней."""
    if not candles:
        return 0

    # Берём последние N дней с ненулевым объёмом
    valid = [c for c in candles if c.get("value", 0) > 0]
    recent = valid[-days:] if len(valid) > days else valid

    if not recent:
        return 0

    total_value = sum(c["value"] for c in recent)
    return total_value / len(recent)


def calculate_spread(bid: float, offer: float) -> float:
    """Рассчитывает bid-ask спред в процентах."""
    if not bid or not offer or bid <= 0:
        return 0
    mid = (bid + offer) / 2
    return round((offer - bid) / mid * 100, 4)


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


def download_company(ticker: str, companies_dir: str, force: bool = False) -> dict:
    """
    Скачивает рыночные данные для одной компании.

    Возвращает dict с результатами:
        {"ok": True/False, "skipped": True/False, "data": dict}
    """
    data_dir = os.path.join(companies_dir, ticker, "data")
    os.makedirs(data_dir, exist_ok=True)

    output_path = os.path.join(data_dir, "moex_market.json")
    result = {"ok": False, "skipped": False, "data": None}

    # Пропускаем если файл уже обновлён сегодня
    if not force and os.path.exists(output_path):
        today = date.today().isoformat()
        file_date = date.fromtimestamp(os.path.getmtime(output_path)).isoformat()
        if file_date == today:
            result["skipped"] = True
            return result

    # 1. Текущие торговые данные
    sec_data = fetch_json(SECURITIES_URL.format(ticker=ticker))
    if not sec_data:
        return result

    parsed = parse_securities_data(sec_data)
    if not parsed:
        return result

    time.sleep(DELAY_SECONDS)

    # 2. Дневные свечи за ~45 дней (чтобы набрать 30 торговых)
    date_till = date.today().isoformat()
    date_from = (date.today() - timedelta(days=60)).isoformat()

    candles_data = fetch_json(
        CANDLES_URL.format(ticker=ticker, date_from=date_from, date_till=date_till)
    )
    candles = parse_candles_data(candles_data) if candles_data else []

    time.sleep(DELAY_SECONDS)

    # 3. Рассчитываем метрики
    adv_30d = calculate_adv(candles, 30)
    spread = calculate_spread(parsed.get("bid", 0), parsed.get("offer", 0))

    # 52-недельные свечи для high/low
    date_from_52w = (date.today() - timedelta(days=370)).isoformat()
    candles_52w_data = fetch_json(
        CANDLES_URL.format(
            ticker=ticker, date_from=date_from_52w, date_till=date_till
        )
    )
    candles_52w = parse_candles_data(candles_52w_data) if candles_52w_data else []

    high_52w = max((c["high"] for c in candles_52w), default=0) if candles_52w else 0
    low_52w = min((c["low"] for c in candles_52w), default=0) if candles_52w else 0

    time.sleep(DELAY_SECONDS)

    # 4. Собираем результат
    market_data = {
        "ticker": ticker,
        "date": date.today().isoformat(),
        "shortname": parsed.get("shortname", ""),
        "secname": parsed.get("secname", ""),
        "price": {
            "last": parsed.get("last", 0),
            "open": parsed.get("open", 0),
            "high": parsed.get("high", 0),
            "low": parsed.get("low", 0),
            "waprice": parsed.get("waprice", 0),
            "prev_close": parsed.get("prevprice", 0),
        },
        "volume": {
            "shares_today": parsed.get("voltoday", 0),
            "value_today_rub": parsed.get("valtoday", 0),
            "num_trades_today": parsed.get("numtrades", 0),
        },
        "liquidity": {
            "adv_30d_rub": round(adv_30d),
            "adv_30d_mln_rub": round(adv_30d / 1_000_000, 1),
            "bid_ask_spread_pct": spread,
        },
        "capitalization": {
            "market_cap_rub": parsed.get("issuecap", 0),
            "market_cap_bln_rub": round(
                parsed.get("issuecap", 0) / 1_000_000_000, 1
            ),
            "shares_outstanding": parsed.get("issuesize", 0),
        },
        "range_52w": {
            "high": high_52w,
            "low": low_52w,
        },
        "listing": {
            "board": parsed.get("board", ""),
            "list_level": parsed.get("listlevel", 0),
            "lot_size": parsed.get("lotsize", 0),
        },
    }

    # Сохраняем
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(market_data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    result["ok"] = True
    result["data"] = market_data
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
    print(f"{CYAN}  Загрузка рыночных данных с MOEX ISS ({date.today().isoformat()}){NC}")
    print(f"{CYAN}═══════════════════════════════════════════════════════════════{NC}")
    print()
    print(f"  Компаний: {len(tickers)}")
    if force:
        print(f"  {YELLOW}Режим --force: перезаписываем существующие{NC}")
    print()

    ok = 0
    skipped = 0
    failed = 0

    for i, ticker in enumerate(tickers, 1):
        prefix = f"  [{i}/{len(tickers)}] {ticker}"

        result = download_company(ticker, companies_dir, force=force)

        if result["skipped"]:
            print(f"{prefix}: {YELLOW}пропуск (уже обновлено сегодня){NC}")
            skipped += 1
        elif result["ok"]:
            d = result["data"]
            price = d["price"]["last"]
            adv = d["liquidity"]["adv_30d_mln_rub"]
            cap = d["capitalization"]["market_cap_bln_rub"]
            spread = d["liquidity"]["bid_ask_spread_pct"]
            print(
                f"{prefix}: {GREEN}OK{NC} — "
                f"цена {price}, ADV {adv}M, кап {cap}B, спред {spread}%"
            )
            ok += 1
        else:
            print(f"{prefix}: {RED}нет данных на MOEX{NC}")
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
