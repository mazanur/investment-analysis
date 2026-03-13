#!/usr/bin/env python3
"""Pre-assemble compact prompt for Claude news-reaction analysis.

Fetches news/impacts from Feeder API, price data from Investment API,
company fundamentals from local _index.md. Outputs a compact prompt to stdout.
Outputs "SKIP" if pre-conditions not met.

Usage:
  python3 prepare_news_context.py TICKER [BASE_DIR]
  python3 prepare_news_context.py TICKER [BASE_DIR] --news-json '{"title":"...", ...}'

Env vars:
  FEEDER_URL  — RSS Feeder API (default: https://feeder.zagirnur.dev)
  API_URL     — Investment API (default: https://investment-api.zagirnur.dev)
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

FEEDER_URL = os.environ.get("FEEDER_URL", "https://feeder.zagirnur.dev")
API_URL = os.environ.get("API_URL", "https://investment-api.zagirnur.dev")

MSK = timezone(timedelta(hours=3))


def _utc_to_msk_date(iso_str: str) -> str:
    """Convert UTC ISO timestamp to MSK date string (YYYY-MM-DD).

    Handles formats: 2026-03-07T22:30:00Z, 2026-03-07T22:30:00+00:00, 2026-03-07
    """
    if not iso_str:
        return ""
    # Already a plain date
    if len(iso_str) == 10:
        return iso_str
    try:
        # Strip trailing Z and parse
        clean = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        # If naive, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(MSK).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        # Fallback: just take first 10 chars
        return iso_str[:10]


_API_ERROR = "__API_ERROR__"


def _curl_json(url: str) -> dict | list | None:
    """Fetch JSON from URL via curl. Returns parsed JSON, None (empty), or _API_ERROR."""
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "10", "-w", "\n%{http_code}", url],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0 or not result.stdout:
            return _API_ERROR
        # Split body and HTTP status code
        parts = result.stdout.rsplit("\n", 1)
        body = parts[0] if len(parts) > 1 else result.stdout
        http_code = parts[1].strip() if len(parts) > 1 else "0"
        if not http_code.startswith("2"):
            return _API_ERROR
        if not body.strip():
            return None
        return json.loads(body)
    except (OSError, json.JSONDecodeError, subprocess.TimeoutExpired):
        return _API_ERROR


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
        if re.match(r"^\s+-\s+", line):
            val = re.sub(r"^\s+-\s+", "", line).strip()
            if current_key and current_list is not None:
                current_list.append(val)
            continue

        kv = re.match(r"^(\w[\w_]*)\s*:\s*(.*)", line)
        if kv:
            if current_key and current_list is not None:
                meta[current_key] = current_list

            key = kv.group(1)
            val = kv.group(2).strip()

            if val == "":
                current_key = key
                current_list = []
            else:
                current_key = key
                current_list = None
                try:
                    meta[key] = int(val)
                except ValueError:
                    try:
                        meta[key] = float(val)
                    except ValueError:
                        meta[key] = val

    if current_key and current_list is not None:
        meta[current_key] = current_list

    return meta


# --- Feeder API ---

def fetch_news(ticker: str, limit: int = 10) -> list[dict]:
    """Fetch news from Feeder API: GET /api/companies/{ticker}/news."""
    data = _curl_json(f"{FEEDER_URL}/api/companies/{ticker}/news?limit={limit}")
    if isinstance(data, dict):
        return data.get("items", [])
    return []


def fetch_impacts(ticker: str, limit: int = 50) -> list[dict]:
    """Fetch impacts from Feeder API: GET /api/companies/{ticker}/impacts."""
    data = _curl_json(f"{FEEDER_URL}/api/companies/{ticker}/impacts?limit={limit}")
    if isinstance(data, dict):
        return data.get("items", [])
    return []


# --- Investment API ---

def fetch_company(ticker: str) -> dict | None:
    """Fetch company data from Investment API."""
    data = _curl_json(f"{API_URL}/companies/{ticker}")
    if data is _API_ERROR:
        return _API_ERROR
    return data if isinstance(data, dict) and "ticker" in data else None


def fetch_prices(ticker: str, limit: int = 30) -> list[dict]:
    """Fetch price history from Investment API. Returns chronological order."""
    data = _curl_json(f"{API_URL}/companies/{ticker}/prices?limit={limit}")
    if data is _API_ERROR:
        return _API_ERROR
    if isinstance(data, list):
        return list(reversed(data))  # API returns newest first
    return []


def fetch_orderbook(ticker: str) -> dict | None:
    """Fetch latest orderbook from Investment API."""
    data = _curl_json(f"{API_URL}/companies/{ticker}/orderbook/latest")
    if data is _API_ERROR:
        return _API_ERROR
    return data if isinstance(data, dict) and "best_bid" in data else None


def fetch_intraday_candles(ticker: str, limit: int = 8) -> list[dict]:
    """Fetch 15-min intraday candles from Investment API."""
    data = _curl_json(f"{API_URL}/companies/{ticker}/candles/intraday?limit={limit}")
    if data is _API_ERROR:
        return _API_ERROR
    return data if isinstance(data, list) else []


def fetch_snapshots(ticker: str, limit: int = 5) -> list[dict]:
    """Fetch hourly snapshots from Investment API."""
    data = _curl_json(f"{API_URL}/companies/{ticker}/snapshots?limit={limit}")
    if data is _API_ERROR:
        return _API_ERROR
    return data if isinstance(data, list) else []


def fetch_catalysts(ticker: str) -> list[dict]:
    """Fetch active catalysts from Investment API."""
    data = _curl_json(f"{API_URL}/companies/{ticker}/catalysts")
    if data is _API_ERROR:
        return _API_ERROR
    return data if isinstance(data, list) else []


def fetch_reports(ticker: str, period_type: str = "yearly", limit: int = 2) -> list[dict]:
    """Fetch financial reports from Investment API."""
    data = _curl_json(f"{API_URL}/companies/{ticker}/reports?period_type={period_type}&limit={limit}")
    if data is _API_ERROR:
        return _API_ERROR
    return data if isinstance(data, list) else []


def fetch_dividends(ticker: str) -> list[dict]:
    """Fetch dividend history from Investment API."""
    data = _curl_json(f"{API_URL}/companies/{ticker}/dividends")
    if data is _API_ERROR:
        return _API_ERROR
    return data if isinstance(data, list) else []


def fetch_sector_peers(sector: str) -> list[dict]:
    """Fetch sector peers from Investment API screener."""
    data = _curl_json(f"{API_URL}/analytics/screener?sector={sector}")
    if data is _API_ERROR:
        return _API_ERROR
    return data if isinstance(data, list) else []


# --- Price helpers ---

def build_price_data(ticker: str, company: dict | None, n_recent: int = 5) -> dict:
    """Build price data dict from API."""
    rows = fetch_prices(ticker, limit=30)
    if rows is _API_ERROR:
        rows = []

    for r in rows:
        r["date"] = str(r.get("date", ""))
        for field in ("open", "high", "low", "close"):
            try:
                r[field] = str(float(r.get(field, 0)))
            except (TypeError, ValueError):
                r[field] = "0"
        try:
            r["volume_rub"] = str(int(float(r.get("volume_rub", 0) or 0)))
        except (TypeError, ValueError):
            r["volume_rub"] = "0"

    adv = 0
    if company and company is not _API_ERROR and company.get("adv_rub_mln"):
        try:
            adv = float(company["adv_rub_mln"]) * 1_000_000
        except (TypeError, ValueError):
            pass

    recent = rows[-n_recent:] if rows else []

    # Last close = last trading day's close price
    last_close = 0.0
    last_close_date = ""
    if rows:
        try:
            last_close = float(rows[-1]["close"])
            last_close_date = rows[-1]["date"]
        except (ValueError, KeyError):
            pass

    # Snapshot price from API (can be more recent than last close)
    snapshot_price = 0.0
    snapshot_ts = ""
    if company and company is not _API_ERROR and company.get("current_price"):
        try:
            snapshot_price = float(company["current_price"])
        except (TypeError, ValueError):
            pass

    return {
        "rows": rows, "recent": recent, "adv": adv,
        "last_close": last_close, "last_close_date": last_close_date,
        "snapshot_price": snapshot_price, "snapshot_ts": snapshot_ts,
    }


def _trading_days_between(date1: str, date2: str) -> int:
    """Count trading days (Mon-Fri) between two YYYY-MM-DD dates (exclusive of date1)."""
    try:
        d1 = datetime.strptime(date1, "%Y-%m-%d")
        d2 = datetime.strptime(date2, "%Y-%m-%d")
    except (ValueError, TypeError):
        return 0
    if d2 <= d1:
        return 0
    count = 0
    cur = d1 + timedelta(days=1)
    while cur <= d2:
        if cur.weekday() < 5:  # Mon=0 .. Fri=4
            count += 1
        cur += timedelta(days=1)
    return count


def find_pre_news_price(rows: list, news_date: str) -> float | None:
    """Find closing price for the trading day before the news date."""
    result = find_pre_news_price_with_date(rows, news_date)
    return result[0] if result else None


def find_pre_news_price_with_date(rows: list, news_date: str) -> tuple[float, str] | None:
    """Find closing price and date for the trading day before the news date."""
    for i, r in enumerate(rows):
        if r["date"] >= news_date and i > 0:
            try:
                return float(rows[i - 1]["close"]), rows[i - 1]["date"]
            except (ValueError, KeyError):
                return None
    if len(rows) >= 2:
        try:
            return float(rows[-2]["close"]), rows[-2]["date"]
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


def find_cluster_start(news_list: list, current_date: str, window_days: int = 7) -> str | None:
    """Find the earliest news published_at date within the last N days."""
    try:
        current_dt = datetime.strptime(current_date, "%Y-%m-%d")
    except ValueError:
        return None

    earliest = current_date
    for n in news_list:
        pub = n.get("published_at", "")
        if not pub:
            continue
        nd = _utc_to_msk_date(pub)
        try:
            nd_dt = datetime.strptime(nd, "%Y-%m-%d")
        except ValueError:
            continue
        if 0 <= (current_dt - nd_dt).days <= window_days and nd < earliest:
            earliest = nd
    return earliest


# --- Pre-news move detection (insider activity) ---

def detect_pre_news_move(snapshots: list, candles: list, news_published_at: str,
                         pre_close: float | None) -> str:
    """Detect suspicious price move BEFORE news publication.

    Compares intraday price just before news timestamp with previous day's close.
    If move > 2% without prior news → flag as potential insider activity.
    Returns warning string or empty.
    """
    if not pre_close or pre_close <= 0:
        return ""
    if not news_published_at:
        return ""

    # Parse news publication time
    try:
        clean = news_published_at.replace("Z", "+00:00")
        news_dt = datetime.fromisoformat(clean)
        if news_dt.tzinfo is None:
            news_dt = news_dt.replace(tzinfo=timezone.utc)
        news_msk = news_dt.astimezone(MSK)
    except (ValueError, TypeError):
        return ""

    news_ts_str = news_msk.strftime("%Y-%m-%dT%H:%M")

    # Find price just before news publication from snapshots or candles
    pre_news_intraday_price = None
    pre_news_ts = ""

    # Try snapshots first (hourly, more reliable)
    if snapshots and snapshots is not _API_ERROR:
        for s in snapshots:
            ts = s.get("timestamp", "")
            if ts and ts[:16] < news_ts_str:
                try:
                    pre_news_intraday_price = float(s.get("price", 0))
                    pre_news_ts = ts[:16]
                except (TypeError, ValueError):
                    pass
                break  # snapshots are newest-first, take the first one before news

    # Try candles if no snapshot found
    if not pre_news_intraday_price and candles and candles is not _API_ERROR:
        for c in candles:
            ts = c.get("timestamp", "")
            if ts and ts[:16] < news_ts_str:
                try:
                    pre_news_intraday_price = float(c.get("close", 0))
                    pre_news_ts = ts[:16]
                except (TypeError, ValueError):
                    pass
                break

    if not pre_news_intraday_price or pre_news_intraday_price <= 0:
        return ""

    move_pct = (pre_news_intraday_price - pre_close) / pre_close * 100

    if abs(move_pct) < 2.0:
        return ""

    direction = "рост" if move_pct > 0 else "падение"
    return (
        f"\u26a0\ufe0f ВНИМАНИЕ: Обнаружено движение цены {direction} {move_pct:+.1f}% "
        f"ДО публикации новости!\n"
        f"Пред. закрытие: {pre_close:.2f} ₽ → Цена до новости ({pre_news_ts}): "
        f"{pre_news_intraday_price:.2f} ₽\n"
        f"Возможна инсайдерская активность — рынок мог отыграть новость заранее. "
        f"Покупка на публикации = покупка на вершине → вероятен skip или осторожный вход."
    )


# --- Index / market context ---

def build_index_context(news_date: str, pre_price: float | None, last_close: float) -> str:
    """Build IMOEX market context for the prompt."""
    index_rows = fetch_prices("IMOEX", limit=10)
    if not index_rows:
        return ""

    for r in index_rows:
        r["date"] = str(r.get("date", ""))
        try:
            r["close"] = str(float(r.get("close", 0)))
        except (TypeError, ValueError):
            r["close"] = "0"

    idx_pre = find_pre_news_price(index_rows, news_date)
    idx_last = 0.0
    idx_last_date = ""
    if index_rows:
        try:
            idx_last = float(index_rows[-1]["close"])
            idx_last_date = index_rows[-1]["date"]
        except (ValueError, KeyError):
            pass

    if not idx_pre or idx_pre <= 0 or idx_last <= 0:
        return ""

    idx_move = (idx_last - idx_pre) / idx_pre * 100
    company_move = 0.0
    if pre_price and pre_price > 0 and last_close > 0:
        company_move = (last_close - pre_price) / pre_price * 100
    relative = company_move - idx_move

    return (
        f"IMOEX: {idx_pre:.0f} → {idx_last:.0f} = {idx_move:+.1f}% "
        f"(close-to-close, до {idx_last_date})\n"
        f"Компания vs рынок: {company_move:+.1f}% vs {idx_move:+.1f}% = "
        f"{relative:+.1f}% ({'outperformance' if relative > 0 else 'underperformance'})"
    )


# --- Sector peers ---

def format_sector_peers(peers: list, exclude_ticker: str, company_pe: float | None) -> str:
    """Format sector peers table from screener data."""
    if peers is _API_ERROR:
        return "[API ERROR]"
    filtered = [p for p in peers if p.get("ticker") != exclude_ticker]
    if not filtered:
        return ""

    lines = ["Тикер | Цена | Upside | P/E | DivYield | Sentiment"]
    pe_values = []
    for p in filtered[:10]:
        t = p.get("ticker", "?")
        price = p.get("current_price", "?")
        upside = p.get("upside")
        upside_str = f"{float(upside):+.0f}%" if upside else "?"
        pe = p.get("p_e")
        pe_str = f"{pe}" if pe else "—"
        if pe:
            pe_values.append(float(pe))
        dy = p.get("dividend_yield")
        dy_str = f"{float(dy):.0f}%" if dy else "—"
        sent = p.get("sentiment", "?")
        lines.append(f"{t} | {price} | {upside_str} | {pe_str} | {dy_str} | {sent}")

    # Median P/E
    if pe_values and company_pe:
        pe_values.sort()
        n = len(pe_values)
        median_pe = (pe_values[n // 2] + pe_values[(n - 1) // 2]) / 2
        discount = (company_pe - median_pe) / median_pe * 100
        lines.append(f"Медианный P/E сектора: {median_pe:.1f}x | P/E компании: {company_pe:.1f}x ({discount:+.0f}%)")

    return "\n".join(lines)


# --- Thesis / Fair Value extraction ---

def extract_business_model(index_path: str) -> str:
    """Extract 'Бизнес-модель' opening paragraph from _index.md (up to 200 chars)."""
    with open(index_path, encoding="utf-8") as f:
        content = f.read()

    m = re.search(r"## Бизнес-модель\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    if not m:
        return ""

    text = m.group(1).strip()
    # Take first meaningful paragraph
    lines = text.split("\n")
    result_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if result_lines:
                break
            continue
        result_lines.append(stripped)

    result = " ".join(result_lines)
    if len(result) > 200:
        result = result[:197] + "..."
    return result


def extract_thesis(index_path: str) -> str:
    """Extract 'Мой тезис' opening paragraph from _index.md (up to 500 chars)."""
    with open(index_path, encoding="utf-8") as f:
        content = f.read()

    # Find thesis section (both naming variants)
    m = re.search(r"## (?:Мой тезис|Инвестиционный тезис)\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    if not m:
        return ""

    text = m.group(1).strip()

    # Skip update headers like "**Обновление 06.03.2026:**"
    lines = text.split("\n")
    result_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if result_lines:
                break  # stop at first empty line after content
            continue
        # Skip update header lines
        if re.match(r"\*\*Обновлени[ея]", stripped):
            continue
        result_lines.append(stripped)

    result = " ".join(result_lines)
    if len(result) > 500:
        result = result[:497] + "..."
    return result


def extract_scenarios(index_path: str) -> str:
    """Extract fair value scenarios table (pessimistic/base/optimistic).

    Only extracts from the FIRST matching table to avoid duplicates
    when multiple valuation methods are present.
    """
    with open(index_path, encoding="utf-8") as f:
        content = f.read()

    # Find scenario table rows (handle bold: **Базовый**)
    scenarios = []
    seen_names = set()
    for m in re.finditer(
        r"\|\s*\*{0,2}(Пессимистичн\w*|Базов\w*|Оптимистичн\w*)\*{0,2}\s*\|(.+)\|",
        content
    ):
        name = m.group(1).strip()
        # Stop at second table (if we see a name we already captured)
        if name in seen_names:
            break
        seen_names.add(name)

        rest = m.group(2).strip()
        # Split into cells and clean bold markers
        cells = [c.strip().replace("**", "").strip() for c in rest.split("|")]
        # Last cell is upside (e.g. "+17%"), second-to-last is price
        # Find last cell containing % — that's the upside
        upside_idx = None
        for i in range(len(cells) - 1, -1, -1):
            if "%" in cells[i] and re.search(r"[+-]?\d+", cells[i]):
                upside_idx = i
                break

        if upside_idx is not None and upside_idx > 0:
            upside = cells[upside_idx].strip()
            # Price is the cell just before upside
            price_raw = cells[upside_idx - 1].strip()
            price = re.sub(r"[^\d.]", "", price_raw.replace(",", "").replace(" ", ""))
            if price:
                scenarios.append(f"{name}: {price} ₽ ({upside})")

    return " | ".join(scenarios) if scenarios else ""


# --- Formatting helpers ---

def _normalize_trigger(text: str) -> str:
    """Normalize trigger text for dedup: lowercase, strip punctuation, collapse spaces."""
    t = text.lower().strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t[:80]


def _dedup_signals(with_signal: list) -> list:
    """Deduplicate signals by normalized trigger text (ignores link differences)."""
    seen = set()
    result = []
    for imp in with_signal:
        ts = imp["trade_signal"]
        trigger = ts.get("trigger", imp.get("title", ""))
        key = (ts.get("signal", ""), _normalize_trigger(trigger))
        if key not in seen:
            seen.add(key)
            result.append(imp)
    return result


def _filter_recent_signals(with_signal: list, max_days: int = 14) -> list:
    """Keep only signals from the last N calendar days."""
    cutoff = (datetime.now() - timedelta(days=max_days)).strftime("%Y-%m-%d")
    return [imp for imp in with_signal
            if imp["trade_signal"].get("date", "9999") >= cutoff]


def format_signals_context(impacts: list) -> str:
    """Format previous trade signals from impacts (no TP/SL numbers to avoid anchoring)."""
    with_signal = [i for i in impacts if i.get("trade_signal")]
    if not with_signal:
        return "Нет предыдущих сигналов."

    with_signal = _dedup_signals(with_signal)
    with_signal = _filter_recent_signals(with_signal)
    if not with_signal:
        return "Нет недавних сигналов (последние 14 дней)."

    def _fmt(imp: dict) -> str:
        ts = imp["trade_signal"]
        return (f"[{ts.get('date', '?')}] {ts.get('signal', '?')}: "
                f"{ts.get('trigger', imp.get('title', '?'))[:100]}")

    lines = ["Последние сигналы (только для проверки дубликатов драйвера):"]
    for imp in with_signal[:5]:
        lines.append(f"- {_fmt(imp)}")

    return "\n".join(lines)


def format_orderbook(ob: dict | None) -> str:
    """Format orderbook data for prompt."""
    if ob is _API_ERROR:
        return "Orderbook: [API ERROR]"
    if not ob:
        return "Orderbook: N/A"
    bid = ob.get("best_bid", "?")
    ask = ob.get("best_ask", "?")
    spread = ob.get("spread_pct", "?")
    return f"Bid: {bid} ₽ | Ask: {ask} ₽ | Spread: {spread}%"


def format_intraday(candles: list) -> str:
    """Format intraday candles for prompt."""
    if not candles:
        return ""
    lines = ["timestamp,open,high,low,close,volume"]
    for c in candles:
        ts = c.get("timestamp", "")
        lines.append(f"{ts},{c.get('open','')},{c.get('high','')},{c.get('low','')},{c.get('close','')},{c.get('volume','')}")
    return "\n".join(lines)


def format_catalysts(catalysts: list) -> str:
    """Format catalysts for prompt."""
    if catalysts is _API_ERROR:
        return "Катализаторы: [API ERROR]"
    if not catalysts:
        return "Нет катализаторов."
    positive = [c for c in catalysts if c.get("impact") == "positive" and c.get("is_active")]
    negative = [c for c in catalysts if c.get("impact") == "negative" and c.get("is_active")]
    lines = []
    if positive:
        lines.append("Позитивные:")
        for c in positive[:5]:
            date_str = f" [{c['date']}]" if c.get("date") else ""
            lines.append(f"  + {c.get('description', '?')}{date_str}")
    if negative:
        lines.append("Негативные:")
        for c in negative[:5]:
            date_str = f" [{c['date']}]" if c.get("date") else ""
            lines.append(f"  - {c.get('description', '?')}{date_str}")
    return "\n".join(lines) if lines else "Нет катализаторов."


def format_financials(company: dict | None, reports: list) -> str:
    """Format key financial metrics from company data and reports."""
    lines = []

    # Market cap
    market_cap = 0.0
    if company and company is not _API_ERROR:
        parts = []
        # Market cap
        mc = company.get("market_cap")
        if mc:
            try:
                market_cap = float(mc)
                if market_cap >= 1_000_000_000_000:
                    parts.append(f"Cap: {market_cap / 1_000_000_000_000:.1f} трлн ₽")
                elif market_cap >= 1_000_000_000:
                    parts.append(f"Cap: {market_cap / 1_000_000_000:.0f} млрд ₽")
                else:
                    parts.append(f"Cap: {market_cap / 1_000_000:.0f} млн ₽")
            except (TypeError, ValueError):
                pass
        for key, label in [("p_e", "P/E"), ("p_bv", "P/BV"), ("roe", "ROE"),
                           ("gov_ownership", "Гос.доля")]:
            val = company.get(key)
            if val is not None:
                suffix = "%" if key in ("roe", "gov_ownership") else ""
                parts.append(f"{label}: {val}{suffix}")
        if parts:
            lines.append(" | ".join(parts))

    if reports and reports is not _API_ERROR:
        r = reports[0]
        extra = r.get("extra_metrics") or {}
        period = r.get("period", "?")

        report_parts = [f"Период: {period}"]
        for key, label in [("revenue", "Выручка"), ("net_income", "ЧП"),
                           ("total_debt", "Общий долг"), ("net_debt", "Чистый долг"),
                           ("equity", "Капитал")]:
            val = r.get(key)
            if val is not None:
                report_parts.append(f"{label}: {val} млрд ₽")

        ebitda = extra.get("ebitda")
        fcf = extra.get("fcf")

        # All extra_metrics (sector-specific: NIM, CoR, loan portfolio, etc.)
        # Exclude already-shown or internal fields
        _skip_extra = {"share_price", "shares_mln", "payout_ratio",
                       "dividend_yield_preferred", "ebitda", "fcf"}
        extra_parts = []
        for k, v in sorted(extra.items()):
            if k in _skip_extra or v is None:
                continue
            extra_parts.append(f"{k}: {v}")
        if extra_parts:
            report_parts.append(" | ".join(extra_parts))

        # Calculated ratios (reports in млрд ₽, market_cap in ₽)
        market_cap_bln = market_cap / 1_000_000_000 if market_cap > 0 else 0
        net_debt = r.get("net_debt")
        if net_debt and ebitda:
            try:
                ebitda_f = float(ebitda)
                nd_f = float(net_debt)
                if ebitda_f > 0:
                    report_parts.append(f"Net Debt/EBITDA: {nd_f / ebitda_f:.1f}x")
                # EV/EBITDA = (market_cap_bln + net_debt) / ebitda
                if market_cap_bln > 0 and ebitda_f > 0:
                    ev = market_cap_bln + nd_f
                    report_parts.append(f"EV/EBITDA: {ev / ebitda_f:.1f}x")
            except (TypeError, ValueError):
                pass

        # FCF yield = fcf / market_cap_bln * 100
        if fcf and market_cap_bln > 0:
            try:
                fcf_yield = float(fcf) / market_cap_bln * 100
                report_parts.append(f"FCF Yield: {fcf_yield:.1f}%")
            except (TypeError, ValueError):
                pass

        lines.append(" | ".join(report_parts))

    if not lines:
        if (company is _API_ERROR) or (reports is _API_ERROR):
            return "Финансовые данные: [API ERROR]"
        return "Финансовые данные: N/A"
    return "\n".join(lines)


def format_dividends(dividends: list, last_close: float, div_yield_fm: float | None) -> str:
    """Format recent dividends with yield calculation."""
    if dividends is _API_ERROR:
        return "Дивиденды: [API ERROR]"
    if not dividends:
        return "Дивиденды: N/A"

    lines = []
    # LTM dividend yield
    now = datetime.now()
    year_ago = now - timedelta(days=365)
    ltm_sum = 0.0
    for d in dividends:
        rd = d.get("record_date", "")
        try:
            dt = datetime.strptime(rd[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        if dt >= year_ago:
            try:
                ltm_sum += float(d.get("amount", 0))
            except (TypeError, ValueError):
                pass

    if div_yield_fm:
        lines.append(f"Div yield (аналитика): {div_yield_fm}%")
    if ltm_sum > 0 and last_close > 0:
        ltm_yield = ltm_sum / last_close * 100
        lines.append(f"LTM DPS: {ltm_sum:.2f} ₽ (yield {ltm_yield:.1f}% к {last_close:.1f} ₽)")

    lines.append("Последние выплаты:")
    for d in dividends[:5]:
        date = d.get("record_date", "?")
        amount = d.get("amount", "?")
        status = d.get("status", "?")
        lines.append(f"  {date}: {amount} ₽ ({status})")

    return "\n".join(lines)


def skip(reason: str):
    """Print SKIP reason to stderr and SKIP to stdout."""
    print(f"Skip: {reason}", file=sys.stderr)
    print("SKIP")


def parse_news_json_arg(args: list[str]) -> dict | None:
    """Parse news JSON from --news-json CLI arg or NEWS_JSON env var."""
    # CLI arg takes priority
    for i, arg in enumerate(args):
        if arg == "--news-json" and i + 1 < len(args):
            try:
                return json.loads(args[i + 1])
            except json.JSONDecodeError:
                return None
    # Fallback: NEWS_JSON env var (used by export_worker via make)
    env_json = os.environ.get("NEWS_JSON", "").strip()
    if env_json:
        try:
            return json.loads(env_json)
        except json.JSONDecodeError:
            return None
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 prepare_news_context.py TICKER [BASE_DIR] [--news-json '{...}']",
              file=sys.stderr)
        sys.exit(1)

    ticker = sys.argv[1]
    # Find base_dir: second arg if it's not a flag
    base_dir = os.getcwd()
    if len(sys.argv) > 2 and not sys.argv[2].startswith("--"):
        base_dir = sys.argv[2]

    index_path = os.path.join(base_dir, "companies", ticker, "_index.md")

    # --- Read local _index.md ---
    if not os.path.exists(index_path):
        skip("No _index.md")
        return

    meta = parse_frontmatter(index_path)

    # --- Get news: either from --news-json or Feeder API ---
    explicit_news = parse_news_json_arg(sys.argv)

    if explicit_news:
        # A4: validate required fields
        _required = ("title", "published_at", "impact_strength")
        _missing = [f for f in _required if not explicit_news.get(f)]
        if _missing:
            skip(f"--news-json missing required fields: {', '.join(_missing)}")
            return
        news = explicit_news
        news_list = [news]
    else:
        news_list = fetch_news(ticker, limit=10)
        if not news_list:
            skip("No news in Feeder API")
            return

        news = None
        for n in news_list:
            strength = n.get("impact_strength", "none")
            if strength in ("medium", "high"):
                news = n
                break

        if not news:
            skip("No news with strength >= medium")
            return

    impacts = fetch_impacts(ticker, limit=50)

    # --- Fetch from Investment API ---
    company = fetch_company(ticker)
    prices = build_price_data(ticker, company)

    # --- Pre-conditions ---
    sentiment = meta.get("sentiment", "")
    if not sentiment:
        skip("Company not analyzed (no sentiment)")
        return

    fair_value = meta.get("my_fair_value")
    try:
        fair_value = float(fair_value)
    except (TypeError, ValueError):
        fair_value = 0
    if fair_value <= 0:
        skip("No fair value estimate")
        return

    adv_mln = prices["adv"] / 1_000_000
    if adv_mln < 50:
        skip(f"Low liquidity: ADV={adv_mln:.0f}M < 50M")
        return

    strength = news.get("impact_strength", "low")

    # --- Price logic (close-to-close) ---
    last_close = prices["last_close"]
    last_close_date = prices["last_close_date"]
    snapshot_price = prices["snapshot_price"]

    # News date from published_at (UTC → MSK)
    news_date = _utc_to_msk_date(news.get("published_at") or "")

    # A3: freshness check — skip if news > 2 trading days old
    today_str = datetime.now(MSK).strftime("%Y-%m-%d")
    if news_date and _trading_days_between(news_date, today_str) > 2:
        skip(f"News too old: {news_date} → {today_str} (> 2 trading days)")
        return

    pre_result = find_pre_news_price_with_date(prices["rows"], news_date)
    pre_price = pre_result[0] if pre_result else None
    pre_price_date = pre_result[1] if pre_result else ""

    # Price move: close-to-close (not snapshot)
    price_move = 0.0
    if pre_price and last_close and pre_price > 0:
        price_move = (last_close - pre_price) / pre_price * 100

    # Upside from last close (categorical for prompt, numeric for pre-filter)
    upside_pct = 0.0
    if last_close > 0 and fair_value > 0:
        upside_pct = (fair_value - last_close) / last_close * 100
    if upside_pct > 30:
        upside_cat = "large (>30%)"
    elif upside_pct > 10:
        upside_cat = "moderate (10-30%)"
    elif upside_pct > 0:
        upside_cat = "small (<10%)"
    else:
        upside_cat = "negative"

    # Cluster price move
    cluster_start = find_cluster_start(news_list, news_date)
    cluster_pre_price = None
    cluster_price_move = 0.0
    if cluster_start and cluster_start != news_date:
        cluster_pre_price = find_pre_news_price(prices["rows"], cluster_start)
        if cluster_pre_price and last_close and cluster_pre_price > 0:
            cluster_price_move = (last_close - cluster_pre_price) / cluster_pre_price * 100

    news_volume = find_news_day_volume(prices["rows"], news_date)
    vol_ratio = 0.0
    if news_volume and prices["adv"] > 0:
        vol_ratio = news_volume / prices["adv"]

    sector = meta.get("sector", "N/A")

    # Recent prices table (OHLC)
    price_table = "date,open,high,low,close,volume_rub\n"
    for r in prices["recent"]:
        price_table += (f"{r.get('date','')},{r.get('open','')},{r.get('high','')},"
                        f"{r.get('low','')},{r.get('close','')},{r.get('volume_rub','')}\n")

    pre_price_str = f"{pre_price:.1f}" if pre_price else "N/A"
    cluster_pre_str = f"{cluster_pre_price:.1f}" if cluster_pre_price else "N/A"

    # Previous signals from impacts
    signals_context = format_signals_context(impacts)

    # Orderbook
    orderbook = fetch_orderbook(ticker)
    orderbook_str = format_orderbook(orderbook)

    # Intraday candles
    intraday_str = ""
    candles = fetch_intraday_candles(ticker)
    if candles is _API_ERROR:
        intraday_str = "[API ERROR]"
    elif candles:
        intraday_str = format_intraday(candles)

    # Snapshots
    snapshots = fetch_snapshots(ticker)
    snapshots_str = ""
    if snapshots is _API_ERROR:
        snapshots_str = "[API ERROR]"
    elif snapshots:
        snap_lines = ["timestamp,price,volume_rub"]
        for s in snapshots:
            snap_lines.append(f"{s.get('timestamp','')},{s.get('price','')},{s.get('volume_rub','')}")
        snapshots_str = "\n".join(snap_lines)
        # Use latest snapshot timestamp
        if not prices["snapshot_ts"] and snapshots:
            prices["snapshot_ts"] = snapshots[0].get("timestamp", "")
            if not snapshot_price:
                try:
                    snapshot_price = float(snapshots[0].get("price", 0))
                except (TypeError, ValueError):
                    pass

    # Pre-news move detection (insider activity)
    pre_news_move_warning = detect_pre_news_move(
        snapshots, candles,
        news.get("published_at", ""),
        pre_price,
    )

    # Catalysts, reports, dividends
    catalysts = fetch_catalysts(ticker)
    catalysts_str = format_catalysts(catalysts)

    reports = fetch_reports(ticker, period_type="yearly", limit=2)
    financials_str = format_financials(company, reports)

    dividends = fetch_dividends(ticker)
    div_yield_fm = meta.get("dividend_yield")
    dividends_str = format_dividends(dividends, last_close, div_yield_fm)

    # Business model, thesis and scenarios from _index.md
    biz_model = extract_business_model(index_path)
    thesis = extract_thesis(index_path)
    scenarios = extract_scenarios(index_path)

    # Sector peers
    sector_peers_str = ""
    if sector and sector != "N/A":
        peers = fetch_sector_peers(sector)
        company_pe = None
        if company and company is not _API_ERROR and company.get("p_e"):
            try:
                company_pe = float(company["p_e"])
            except (TypeError, ValueError):
                pass
        sector_peers_str = format_sector_peers(peers, ticker, company_pe)

    # Market context (IMOEX)
    index_context = build_index_context(news_date, pre_price, last_close)

    # News summary
    impact_summary = news.get("impact_summary", "")
    news_summary = news.get("summary", "")

    # Staleness: similar earlier articles (from export_worker)
    staleness_section = ""
    similar_earlier = news.get("similar_earlier_news")
    if similar_earlier and isinstance(similar_earlier, list):
        lines_st = ["## ⚠️ Похожие более ранние публикации"]
        lines_st.append("Следующие статьи на ту же тему вышли РАНЬШЕ текущей новости.")
        lines_st.append("Если рынок уже отреагировал на них — текущая новость может быть stale (повторная публикация).")
        for item in similar_earlier:
            sim_pct = int(item.get("similarity", 0) * 100)
            lines_st.append(f"- [{item.get('source', '?')}] {item.get('published_at', '?')[:16]} — {item.get('title', '?')} (similarity: {sim_pct}%)")
        lines_st.append("**Учти это при оценке \"Уже в цене?\" — если первоисточник вышел часы назад, рынок мог уже отреагировать.**")
        staleness_section = "\n" + "\n".join(lines_st) + "\n"

    # --- Build prompt ---
    # Price section (close-to-close)
    snapshot_line = ""
    if snapshot_price and snapshot_price != last_close:
        snap_ts = prices.get("snapshot_ts", "")
        # A5: stale snapshot warning
        stale_label = ""
        if snap_ts:
            snap_date = _utc_to_msk_date(snap_ts)
            if snap_date and snap_date != today_str:
                days_stale = _trading_days_between(snap_date, today_str)
                if days_stale > 1:
                    stale_label = " [STALE: >1 trading day]"
                else:
                    try:
                        snap_dt = datetime.strptime(snap_date, "%Y-%m-%d")
                        if snap_dt.weekday() >= 5:  # Sat/Sun
                            stale_label = " [STALE: weekend]"
                    except ValueError:
                        pass
        snapshot_line = f"\nПоследний snapshot ({snap_ts[:16]}): {snapshot_price:.2f} ₽{stale_label}"

    # B5: explicit pre_news_price label
    pre_news_line = ""
    if pre_price:
        pre_news_line = f"\nPre-news price: {pre_price:.2f} ₽ ({pre_price_date} close)"

    # B2: intraday metrics from OHLC on news day
    intraday_ohlc_line = ""
    for r in prices["rows"]:
        if r["date"] >= news_date:
            try:
                day_low = float(r["low"])
                day_high = float(r["high"])
                day_open = float(r["open"])
                day_close = float(r["close"])
                if day_low > 0 and day_high > 0:
                    intraday_range = (day_high - day_low) / day_low * 100
                    intraday_ohlc_line += f"\nIntraday range ({r['date']}): {day_low:.2f}–{day_high:.2f} = {intraday_range:.1f}%"
                if day_open > 0:
                    open_to_close = (day_close - day_open) / day_open * 100
                    intraday_ohlc_line += f" | Open-to-close: {open_to_close:+.1f}%"
            except (ValueError, KeyError):
                pass
            break

    pre_news_move_section = ""
    if pre_news_move_warning:
        pre_news_move_section = f"\n{pre_news_move_warning}\n"

    price_section = (
        f"Цена закрытия ({last_close_date}): {last_close:.2f} ₽{snapshot_line}"
        f"{pre_news_line}\n"
        f"Price move (close-to-close): {price_move:+.1f}% "
        f"(от {pre_price_str} до {last_close:.2f} ₽){intraday_ohlc_line}\n"
        f"Volume ratio: {vol_ratio:.1f}x ADV | ADV: {adv_mln:.0f}M ₽"
        f"{pre_news_move_section}"
    )

    # Business model + Thesis section
    biz_model_line = ""
    if biz_model:
        biz_model_line = f"\nБизнес-модель: {biz_model}\n"

    thesis_section = ""
    if thesis or scenarios:
        thesis_section = "\n## Инвестиционный тезис\n"
        if thesis:
            thesis_section += thesis + "\n"
        if scenarios:
            thesis_section += f"\nСценарии fair value: {scenarios}\n"

    # Sector section
    sector_section = ""
    if sector_peers_str:
        peer_count = sector_peers_str.count("\n")
        sector_section = f"\n## Сектор: {sector} ({peer_count} компаний)\n{sector_peers_str}\n"

    # Market context section
    market_section = ""
    if index_context:
        market_section = f"\n## Рыночный контекст\n{index_context}\n"

    cluster_section = ""
    if cluster_pre_price and cluster_start != news_date:
        cluster_section = f"""
## Кластер новостей (накопленное движение)
Первая новость кластера: {cluster_start} | Цена до кластера: {cluster_pre_str} ₽
Накопленный price_move: {cluster_price_move:+.1f}% (с {cluster_pre_str} до {last_close:.2f} ₽)
ВАЖНО: если накопленный price_move > 2% при позитивных новостях — позитив УЖЕ В ЦЕНЕ → skip.
Если накопленный price_move < -5% при негативных — возможен long-oversold."""

    signals_section = f"\n## Предыдущие сигналы\n{signals_context}"

    orderbook_section = f"\n## Orderbook\n{orderbook_str}"

    intraday_section = ""
    if intraday_str:
        intraday_section = f"\n## Интрадей свечи (15 мин, Tinkoff)\n{intraday_str}"

    snapshots_section = ""
    if snapshots_str:
        snapshots_section = f"\n## Снэпшоты (часовые)\n{snapshots_str}"

    prompt = f"""Ты — трейдер-аналитик. Определи, есть ли спекулятивная возможность на 1-2 торговых дня.

**ВАЖНО: Анализируй ТОЛЬКО влияние конкретной новости на компанию. Fair value, upside и предыдущие сигналы — это контекст, НЕ основание для сигнала. Если новость = шум или косвенное влияние для этой компании → skip, даже если upside большой или были предыдущие buy.**

## Правила (прочитай ПЕРЕД анализом данных)

**Классификация новости:**
| Тип | Примеры | Влияние | Реалистичный TP (1-2 дня) |
|-----|---------|---------|--------------------------|
| results | Квартальный/годовой отчёт с beat/miss | Сильное | +2–5% |
| results-routine | Ежемесячный РПБУ, операционные данные | Слабое-среднее | +1–2% |
| dividends | Решение о дивидендах, размер, дата | Среднее-сильное | +2–4% |
| regulation | Санкции, налоги, тарифы, законы | Сильное | +2–5% |
| corporate | M&A, buyback, допэмиссия, крупные контракты | Сильное | +3–7% |
| macro | Ставка ЦБ, курс, геополитика | Среднее | +1–3% |
| noise | Мнения аналитиков, пересказ старого, прогнозы | Слабое → **skip** |  |

**Маркеры noise (→ skip):** заголовок содержит "МНЕНИЕ:", "Ожидаем", "Прогноз:", "Обзор:", аналитик прогнозирует без новых фактов, пересказ вчерашней новости другими словами.

**"Уже в цене?" — матрица:**
| price_move (абс.) | volume > 2× ADV | Вердикт |
|--------------------|-----------------|---------|
| < 2% | — | Окно открыто |
| 2–5% | Нет | Частично в цене |
| 2–5% | Да | В цене → skip (позитив) или ищи перепроданность (негатив) |
| > 5% | — | Сильная реакция → перепроданность/перекупленность |

**Инсайдерская активность (pre-news move):**
Если в секции «Движение цены» есть предупреждение о движении ДО публикации новости (⚠️ ВНИМАНИЕ) — это значит цена двигалась до выхода новости. На российском рынке это частое явление (инсайдеры). Если pre-news move > 2% в направлении новости → считай что новость УЖЕ В ЦЕНЕ → skip для long-positive/short-negative. Покупка на публикации = покупка на вершине.

**4 сценария (СТРОГО по направлению новости):**
- Позитивная новость → ТОЛЬКО long-positive или short-overbought. НИКОГДА short-negative.
- Негативная новость → ТОЛЬКО long-oversold (если > 5% падение) или short-negative. НИКОГДА long-positive.
- Если направление новости не совпадает ни с одним сценарием → skip.

1. **long-positive**: ПОЗИТИВ + price_move < 2% + нет кластера → покупка до реакции
2. **long-oversold**: НЕГАТИВ + price_move > 5% ВНИЗ + фундаментал НЕ сломан → покупка на панике
3. **short-negative**: НЕГАТИВ + price_move < 2% + фундаментал сломан/ухудшен → шорт до реакции
4. **short-overbought**: ПОЗИТИВ + price_move > 5% ВВЕРХ + upside small → шорт перекупленности

**Target (горизонт 1-2 дня) — КАЛИБРУЙ ПО ТИПУ НОВОСТИ:**
- long-positive: используй "Реалистичный TP" из таблицы классификации выше (НЕ 3-7% для всех)
  - results-routine (РПБУ, операционные): +1–2%
  - macro/commodity: +1–3%
  - results (квартальный beat): +2–5%
  - corporate (M&A, buyback): +3–7%
- long-oversold: частичный возврат к pre_news_price (30-50% от падения)
- short-negative: аналогично long-positive, но вниз
- short-overbought: частичный возврат к pre_news_price (30-50% от роста)
**ЗАПРЕЩЕНО** использовать fair value, сценарии оценки или upside как target. Target = краткосрочное ценовое движение за 1-2 дня, а не фундаментальная переоценка.
**МАКСИМУМ TP: ±10% от entry.** Если ты считаешь что upside больше — это позиционный трейд, а не news-reaction → skip.

**Stop-loss (1.5-3% от entry):**
- long: entry × 0.97–0.985 (или минимум дня для long-oversold, если он ближе)
- short: entry × 1.015–1.03 (или максимум дня для short-overbought, если он ближе)
- **МАКСИМУМ SL: 5% от entry.** SL > 5% = позиционный трейд → skip.

**Обязательные условия (любое нарушение → skip):**
- confidence ≥ medium (low → skip)
- risk_reward ≥ 1.5
- ADV ≥ 50M ₽ (для шортов: ADV > 200M)
- Strength ≥ medium (pre-filtered)
- Новость ≤ 2 торговых дней (pre-filtered)
- Фундаментальный тезис не сломан (для long)
- Кластер price_move < 2% (для long-positive)
- Если по той же теме уже есть buy/sell сигнал (см. «Предыдущие сигналы») → skip (позиция уже открыта, не дублируй)

**Фундаментал — новость меняет тезис?**
- Ломает (делистинг, дефолт, SDN) → skip
- Усиливает (рекордная прибыль, неожиданные дивиденды) → торгуем уверенно
- Временная (штраф, блокировка) → торгуем если цена перереагировала
- Шум → skip

**R/R для short:**
expected_return = (entry - target) / entry; risk = (stop_loss - entry) / entry

**Размер позиции:**
- high confidence (R/R > 2.5): full (до 5% портфеля)
- medium confidence (R/R 1.5-2.5): half (до 3% портфеля)
- low confidence (R/R < 1.5): skip

---

## Компания: {ticker}
Sector: {sector} | Sentiment: {sentiment} | Upside: {upside_cat}
{biz_model_line}{thesis_section}
## Финансовые показатели
{financials_str}

## Дивиденды
{dividends_str}

## Катализаторы
{catalysts_str}

## Новость (только заголовок — для оценки релевантности на Шаге 0)
{news.get('published_at', news_date)} | {news.get('title', '')}
Strength: {strength} | URL: {news.get('link', '')}

## Детали новости (читай ТОЛЬКО после прохождения Шага 0)
*(Оцени ПРЯМОЕ влияние именно этой новости на {ticker}. Косвенное макро ≠ прямое событие.)*
{news_summary}
Impact-анализ (мнение LLM-фильтра, может быть неточным): {impact_summary}
{staleness_section}
## Движение цены
{price_section}

{price_table}{orderbook_section}
{intraday_section}
{snapshots_section}
{market_section}{sector_section}{cluster_section}{signals_section}

---

## Задание

**НАПОМИНАНИЕ: Анализируй ТОЛЬКО эту конкретную новость. Предыдущие сигналы и fair value — контекст, НЕ основание. Не наследуй entry/TP/SL из старых сигналов.**

Проведи анализ по шагам в блоке <analysis>. **Если шаг 0 или 1 дал skip — ОСТАНОВИСЬ, напиши reasoning и сразу выведи skip JSON.**

0. **Релевантность:** Прочитай заголовок новости и бизнес-модель компании. Новость влияет на КЛЮЧЕВОЙ ДРАЙВЕР ВЫРУЧКИ этой компании?
   - ДА (прямое): компания названа по имени; событие внутри компании; новость о товаре/рынке который компания ПРОДАЁТ (нефть для нефтекомпании, кредиты для банка); регулятор меняет правила для этой компании → продолжай.
   - НЕТ (косвенное): новость о товаре который компания НЕ продаёт (цена нефти для трубопроводной/тарифной компании); общая геополитика без адресного влияния; мнения аналитиков о секторе → skip.
   - Подсказка: сверься с «Бизнес-модель» — если там написано "тарифная монополия", то новость о ценах на commodity = косвенное. Если "нефтедобыча", то цена нефти = прямое.
1. **Дубликат драйвера:** Есть ли в «Предыдущих сигналах» buy/sell с тем же БАЗОВЫМ ДРАЙВЕРОМ? Базовый драйвер = корневая причина влияния на цену. Пример: "Brent упал на 3%" и "Франция продаёт нефтяные запасы" — один драйвер (цена нефти). "МСФО отчёт" и "дивиденды" — разные драйверы. Если тот же драйвер → skip.
2. **Классификация:** (теперь прочитай «Детали новости») тип новости, сила, направление
3. **"Уже в цене?":** price_move + volume_ratio → вердикт по матрице
4. **Фундаментал:** новость ломает/усиливает/временная/шум?
5. **Сценарий:** какой из 4 подходит? Если ни один → skip
6. **Trade setup + решение:** entry, target (1-2 дня), stop-loss (2-4%), R/R, signal, confidence, position_size
7. **Самопроверка (обязательно):** Перед выводом JSON проверь:
   - confidence ≥ medium? Если low → skip
   - risk_reward ≥ 1.5? Если нет → skip
   - Если новость негативная → signal НЕ может быть buy (кроме long-oversold при падении >5%)
   - Если новость позитивная → signal НЕ может быть sell (кроме short-overbought при росте >5%)
   - **TP калиброван по типу новости?** Ежемесячный РПБУ не может давать TP +5%. Commodity news не может давать TP +7%. Сверься с таблицей классификации.
   - **TP ≤ 10% от entry?** Если больше — это не news-reaction, а позиционный трейд → skip.
   - **SL ≤ 5% от entry?** Если больше → skip.
   - stop_loss в пределах 1.5-3% от entry
   - **Есть ли staleness warning?** Если да — усиль оценку "Уже в цене?". Новость вышла часы назад → вероятно уже отыграна.
   - Если news_type = noise → signal ОБЯЗАН быть skip. "МНЕНИЕ:", "Прогноз:", аналитические обзоры без новых фактов = noise.
   - Если проверка не пройдена → исправь или переведи в skip

<analysis>
Шаг 0: Релевантность —

После блока </analysis> выведи ТОЛЬКО валидный JSON (без ```json```, без текста до/после):
{{"date": "YYYY-MM-DD", "trigger": "краткое описание", "trigger_url": "url",
"news_type": "results|dividends|regulation|corporate|macro|noise",
"signal": "buy|sell|skip", "direction": "long-positive|long-oversold|short-negative|short-overbought|skip",
"confidence": "high|medium|low",
"entry": {{"condition": "описание", "price": число}},
"exit": {{"take_profit": число, "stop_loss": число, "time_limit_days": 2}},
"expected_return_pct": число, "risk_reward_ratio": число,
"position_size": "full|half|skip", "reasoning": "обоснование"}}

Если signal = skip: entry=null, exit=null, expected_return_pct=0, risk_reward_ratio=0, position_size="skip"."""

    print(prompt)


if __name__ == "__main__":
    main()
