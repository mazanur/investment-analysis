#!/usr/bin/env python3
"""Pre-assemble compact prompt for Claude news-reaction analysis.

Reads company data, calculates metrics, outputs a compact prompt.
Outputs "SKIP" (+ writes skip record) if pre-conditions not met.

Usage: python3 prepare_news_context.py TICKER [BASE_DIR]
"""
import csv
import json
import os
import re
import statistics
import subprocess
import sys
from datetime import datetime, timezone


def parse_frontmatter(path: str) -> dict:
    """Parse YAML frontmatter from _index.md using stdlib only."""
    with open(path, encoding="utf-8") as f:
        content = f.read()

    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return {}

    text = m.group(1)
    meta = {}
    current_key = None
    current_list = None

    for line in text.split("\n"):
        # List item
        if re.match(r"^\s+-\s+", line):
            val = re.sub(r"^\s+-\s+", "", line).strip()
            if current_key and current_list is not None:
                current_list.append(val)
            continue

        # Key-value pair
        kv = re.match(r"^(\w[\w_]*)\s*:\s*(.*)", line)
        if kv:
            # Save previous list
            if current_key and current_list is not None:
                meta[current_key] = current_list

            key = kv.group(1)
            val = kv.group(2).strip()

            if val == "":
                # Next lines might be a list
                current_key = key
                current_list = []
            else:
                current_key = key
                current_list = None
                # Try numeric
                try:
                    meta[key] = int(val)
                except ValueError:
                    try:
                        meta[key] = float(val)
                    except ValueError:
                        meta[key] = val

    # Save last list
    if current_key and current_list is not None:
        meta[current_key] = current_list

    return meta


def read_price_history(path: str, n_recent: int = 5, n_adv: int = 30) -> dict:
    """Read price_history.csv, return recent rows, ADV, and full rows for lookup."""
    if not os.path.exists(path):
        return {"rows": [], "recent": [], "adv": 0}

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return {"rows": [], "recent": [], "adv": 0}

    # ADV = median volume_rub over last n_adv rows
    volumes = []
    for r in rows[-n_adv:]:
        v = r.get("volume_rub", "")
        if v:
            try:
                volumes.append(int(v))
            except ValueError:
                pass
    adv = statistics.median(volumes) if volumes else 0

    # Recent rows for prompt
    recent = rows[-n_recent:]

    return {"rows": rows, "recent": recent, "adv": adv}


def find_pre_news_price(rows: list, news_date: str) -> float | None:
    """Find closing price for the trading day before the news date."""
    for i, r in enumerate(rows):
        if r["date"] >= news_date and i > 0:
            try:
                return float(rows[i - 1]["close"])
            except (ValueError, KeyError):
                return None
    # If news_date is after all rows, use second-to-last
    if len(rows) >= 2:
        try:
            return float(rows[-2]["close"])
        except (ValueError, KeyError):
            return None
    return None


def find_news_day_volume(rows: list, news_date: str) -> int | None:
    """Find volume on the news date (or closest trading day after)."""
    for r in rows:
        if r["date"] >= news_date:
            try:
                return int(r["volume_rub"])
            except (ValueError, KeyError):
                return None
    return None


def find_cluster_start(news_list: list, current_news: dict, window_days: int = 7) -> str | None:
    """Find the earliest news date within the last N days — start of the cluster."""
    current_date = current_news.get("date", "")
    if not current_date:
        return None
    try:
        current_dt = datetime.strptime(current_date, "%Y-%m-%d")
    except ValueError:
        return None

    earliest = current_date
    for n in news_list:
        nd = n.get("date", "")
        if not nd:
            continue
        try:
            nd_dt = datetime.strptime(nd, "%Y-%m-%d")
        except ValueError:
            continue
        if 0 <= (current_dt - nd_dt).days <= window_days and nd < earliest:
            earliest = nd
    return earliest


def read_recent_signals(signals_path: str, n: int = 5) -> list:
    """Read the most recent N signals from trade_signals.json."""
    if not os.path.exists(signals_path):
        return []
    with open(signals_path, encoding="utf-8") as f:
        try:
            signals = json.load(f)
        except json.JSONDecodeError:
            return []
    return signals[:n]


def format_signals_context(signals: list) -> str:
    """Format recent signals as compact text for the prompt."""
    if not signals:
        return "Нет предыдущих сигналов."
    lines = []
    for s in signals:
        sig = s.get("signal", "?")
        date = s.get("date", "?")
        trigger = s.get("trigger", "?")[:80]
        reasoning = s.get("reasoning", "")[:120]
        lines.append(f"- [{date}] {sig}: {trigger} | {reasoning}")
    return "\n".join(lines)


def fetch_last_price_moex(ticker: str) -> float | None:
    """Fetch last traded price from MOEX ISS API (single HTTP call, no auth)."""
    url = (
        f"http://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR"
        f"/securities/{ticker}.json?iss.meta=off&iss.json=extended"
    )
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "10", url],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0 or not result.stdout:
            return None
        data = json.loads(result.stdout)
        for block in data:
            if not isinstance(block, dict):
                continue
            marketdata = block.get("marketdata")
            if marketdata and isinstance(marketdata, list):
                for row in marketdata:
                    if isinstance(row, dict) and row.get("SECID") == ticker:
                        return row.get("LAST") or row.get("LCLOSEPRICE")
    except (OSError, json.JSONDecodeError, subprocess.TimeoutExpired):
        pass
    return None


def write_skip_signal(signals_path: str, reason: str, news: dict) -> None:
    """Write a skip signal to trade_signals.json."""
    signal = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "trigger": news.get("title", "N/A"),
        "trigger_url": news.get("url", ""),
        "signal": "skip",
        "direction": "skip",
        "confidence": "low",
        "entry": None,
        "exit": None,
        "expected_return_pct": None,
        "risk_reward_ratio": None,
        "position_size": "skip",
        "reasoning": f"Pre-filter: {reason}",
    }

    existing = []
    if os.path.exists(signals_path):
        with open(signals_path, encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []

    existing.insert(0, signal)

    with open(signals_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 prepare_news_context.py TICKER [BASE_DIR]", file=sys.stderr)
        sys.exit(1)

    ticker = sys.argv[1]
    base_dir = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    company_dir = os.path.join(base_dir, "companies", ticker)
    data_dir = os.path.join(company_dir, "data")
    index_path = os.path.join(company_dir, "_index.md")
    news_path = os.path.join(data_dir, "news.json")
    price_path = os.path.join(data_dir, "price_history.csv")
    signals_path = os.path.join(data_dir, "trade_signals.json")

    # --- Read data ---
    if not os.path.exists(index_path):
        print("SKIP")
        return

    meta = parse_frontmatter(index_path)

    if not os.path.exists(news_path):
        print("SKIP")
        return

    with open(news_path, encoding="utf-8") as f:
        news_list = json.load(f)

    if not news_list:
        print("SKIP")
        return

    news = news_list[-1]  # Latest news entry (appended at end)

    prices = read_price_history(price_path)

    # --- Pre-conditions ---
    sentiment = meta.get("sentiment", "")
    if not sentiment:
        write_skip_signal(signals_path, "Company not analyzed (no sentiment)", news)
        print("SKIP")
        return

    fair_value = meta.get("my_fair_value")
    try:
        fair_value = float(fair_value)
    except (TypeError, ValueError):
        fair_value = 0
    if fair_value <= 0:
        write_skip_signal(signals_path, "No fair value estimate", news)
        print("SKIP")
        return

    adv_mln = prices["adv"] / 1_000_000
    if adv_mln < 50:
        write_skip_signal(signals_path, f"Low liquidity: ADV={adv_mln:.0f}M < 50M", news)
        print("SKIP")
        return

    strength = news.get("strength", "low")
    if strength == "low":
        write_skip_signal(signals_path, "News strength=low", news)
        print("SKIP")
        return

    # --- Calculate metrics ---

    # Actual price: MOEX live → price_history.csv → frontmatter
    current_price = fetch_last_price_moex(ticker) or 0.0
    price_source = "moex"
    if current_price <= 0 and prices["rows"]:
        try:
            current_price = float(prices["rows"][-1]["close"])
            price_source = "csv"
        except (ValueError, KeyError):
            pass
    if current_price <= 0:
        try:
            current_price = float(meta.get("current_price", 0))
            price_source = "frontmatter"
        except (TypeError, ValueError):
            current_price = 0

    news_date = news.get("date", "")
    pre_price = find_pre_news_price(prices["rows"], news_date)
    price_move = 0.0
    if pre_price and current_price and pre_price > 0:
        price_move = (current_price - pre_price) / pre_price * 100

    # Cluster price move: accumulated move since first news in the last 7 days
    cluster_start = find_cluster_start(news_list, news)
    cluster_pre_price = None
    cluster_price_move = 0.0
    if cluster_start and cluster_start != news_date:
        cluster_pre_price = find_pre_news_price(prices["rows"], cluster_start)
        if cluster_pre_price and current_price and cluster_pre_price > 0:
            cluster_price_move = (current_price - cluster_pre_price) / cluster_pre_price * 100

    news_volume = find_news_day_volume(prices["rows"], news_date)
    vol_ratio = 0.0
    if news_volume and prices["adv"] > 0:
        vol_ratio = news_volume / prices["adv"]

    # Recalculate upside from actual price
    upside_pct = 0.0
    if current_price > 0 and fair_value > 0:
        upside_pct = (fair_value - current_price) / current_price * 100

    ev_ebitda = meta.get("ev_ebitda", "N/A")
    div_yield = meta.get("dividend_yield", "N/A")
    position = meta.get("position", "N/A")
    sector = meta.get("sector", "N/A")

    risks = meta.get("key_risks", [])
    opps = meta.get("key_opportunities", [])
    risks_str = "; ".join(risks[:5]) if risks else "N/A"
    opps_str = "; ".join(opps[:5]) if opps else "N/A"

    # Recent prices table
    price_table = "date,close,volume_rub\n"
    for r in prices["recent"]:
        price_table += f"{r.get('date','')},{r.get('close','')},{r.get('volume_rub','')}\n"

    pre_price_str = f"{pre_price:.1f}" if pre_price else "N/A"
    cluster_pre_str = f"{cluster_pre_price:.1f}" if cluster_pre_price else "N/A"

    # Recent signals for context
    recent_signals = read_recent_signals(signals_path)
    signals_context = format_signals_context(recent_signals)

    # --- Build prompt ---
    cluster_section = ""
    if cluster_pre_price and cluster_start != news_date:
        cluster_section = f"""
## Кластер новостей (накопленное движение)
Первая новость кластера: {cluster_start} | Цена до кластера: {cluster_pre_str} ₽
Накопленный price_move: {cluster_price_move:+.1f}% (с {cluster_pre_str} до {current_price} ₽)
ВАЖНО: если накопленный price_move > 2% при позитивных новостях — позитив УЖЕ В ЦЕНЕ → skip.
Если накопленный price_move < -5% при негативных — возможен long-oversold."""

    signals_section = f"""
## Предыдущие сигналы (последние 5)
{signals_context}
ВАЖНО: если по той же теме уже были skip-ы — новая новость той же темы тоже skip."""

    prompt = f"""Ты — трейдер-аналитик. Определи, есть ли спекулятивная возможность.

## Компания: {ticker}
Sector: {sector} | Sentiment: {sentiment} | Position: {position}
Fair value: {fair_value} ₽ | Текущая цена: {current_price} ₽ ({price_source}) | Upside: {upside_pct:+.1f}%
EV/EBITDA: {ev_ebitda} | Div yield: {div_yield}

Риски: {risks_str}
Возможности: {opps_str}

## Новость
{news.get('date', '')} | {news.get('title', '')}
{news.get('summary', '')}
Strength: {strength} | Action: {news.get('action', 'N/A')} | URL: {news.get('url', '')}

## Движение цены (от предыдущего дня)
До новости: {pre_price_str} ₽ → Сейчас: {current_price} ₽ = {price_move:+.1f}%
Volume ratio: {vol_ratio:.1f}x ADV | ADV: {adv_mln:.0f}M ₽

{price_table}{cluster_section}
{signals_section}

## Правила
- Сначала проверь КЛАСТЕРНЫЙ price_move (если есть). Если накопленный move > 2% при позитиве → позитив в цене → skip
- price_move < 2% + позитив + НЕТ кластера → long-positive (покупка до реакции рынка)
- price_move < -5% + негатив + фундаментал цел → long-oversold (покупка на панике)
- R/R < 2.0 → skip. Новость ломает тезис (делистинг, дефолт, потеря лицензии) → skip
- Новость повторяет тему предыдущих skip-ов → skip (не переоценивать ту же информацию)
- Stop-loss: -10% от entry (отчёт/регуляторика), -5% (дивиденды)
- Target: fair_value для long-positive, pre_news_price для long-oversold
- Time limit: 5-10 дней (positive), 10-20 дней (oversold)
- Confidence high → full (5% портфеля), medium → half (3%), low → skip

## Задание
Добавь сигнал В НАЧАЛО массива в {signals_path}.
JSON-формат сигнала:
{{"date": "YYYY-MM-DD", "trigger": "краткое описание", "trigger_url": "url",
"signal": "buy|skip", "direction": "long-positive|long-oversold|skip",
"confidence": "high|medium|low",
"entry": {{"condition": "описание", "price": число}},
"exit": {{"take_profit": число, "stop_loss": число, "time_limit_days": число}},
"expected_return_pct": число, "risk_reward_ratio": число,
"position_size": "full|half|skip", "reasoning": "обоснование"}}"""

    print(prompt)


if __name__ == "__main__":
    main()
