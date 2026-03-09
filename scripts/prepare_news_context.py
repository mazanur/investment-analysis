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

def format_signals_context(impacts: list) -> str:
    """Format previous trade signals from impacts."""
    with_signal = [i for i in impacts if i.get("trade_signal")]
    if not with_signal:
        return "Нет предыдущих сигналов."

    def _fmt(imp: dict) -> str:
        ts = imp["trade_signal"]
        return (f"[{ts.get('date', '?')}] {ts.get('signal', '?')}: "
                f"{ts.get('trigger', imp.get('title', '?'))[:80]} | "
                f"{ts.get('reasoning', '')[:120]}")

    lines = []

    # Last BUY
    last_buy = next((i for i in with_signal if i["trade_signal"].get("signal") == "buy"), None)
    if last_buy:
        ts = last_buy["trade_signal"]
        entry = ts.get("entry", {}) or {}
        exit_ = ts.get("exit", {}) or {}
        lines.append(f"Последний BUY: {_fmt(last_buy)}")
        lines.append(f"  Entry: {entry.get('price', '?')} ₽ | TP: {exit_.get('take_profit', '?')} ₽ | SL: {exit_.get('stop_loss', '?')} ₽ | R/R: {ts.get('risk_reward_ratio', '?')}")
    else:
        lines.append("Последний BUY: не было")

    # Last SELL
    last_sell = next((i for i in with_signal if i["trade_signal"].get("signal") == "sell"), None)
    if last_sell:
        lines.append(f"Последний SELL: {_fmt(last_sell)}")

    # Last 3 signals (any type)
    lines.append("Последние сигналы:")
    for imp in with_signal[:3]:
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

    if company and company is not _API_ERROR:
        parts = []
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
                           ("net_debt", "Чистый долг"), ("equity", "Капитал")]:
            val = r.get(key)
            if val is not None:
                report_parts.append(f"{label}: {val} млрд ₽")

        ebitda = extra.get("ebitda")
        fcf = extra.get("fcf")
        if ebitda:
            report_parts.append(f"EBITDA: {ebitda} млрд ₽")
        if fcf:
            report_parts.append(f"FCF: {fcf} млрд ₽")

        net_debt = r.get("net_debt")
        if net_debt and ebitda and float(ebitda) > 0:
            nd_ebitda = float(net_debt) / float(ebitda)
            report_parts.append(f"Net Debt/EBITDA: {nd_ebitda:.1f}x")

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


def read_guide(base_dir: str) -> str:
    """Read NEWS_REACTION_GUIDE.md as methodology for the prompt."""
    guide_path = os.path.join(base_dir, "companies", "NEWS_REACTION_GUIDE.md")
    if not os.path.exists(guide_path):
        return ""
    with open(guide_path, encoding="utf-8") as f:
        return f.read()


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

    # Upside from last close
    upside_pct = 0.0
    if last_close > 0 and fair_value > 0:
        upside_pct = (fair_value - last_close) / last_close * 100

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

    position = meta.get("position", "N/A")
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

    # Catalysts, reports, dividends
    catalysts = fetch_catalysts(ticker)
    catalysts_str = format_catalysts(catalysts)

    reports = fetch_reports(ticker, period_type="yearly", limit=2)
    financials_str = format_financials(company, reports)

    dividends = fetch_dividends(ticker)
    div_yield_fm = meta.get("dividend_yield")
    dividends_str = format_dividends(dividends, last_close, div_yield_fm)

    # Thesis and scenarios from _index.md
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

    # Methodology guide
    guide = read_guide(base_dir)

    # News summary
    impact_summary = news.get("impact_summary", "")
    news_summary = news.get("summary", "")

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

    price_section = (
        f"Цена закрытия ({last_close_date}): {last_close:.2f} ₽{snapshot_line}"
        f"{pre_news_line}\n"
        f"Price move (close-to-close): {price_move:+.1f}% "
        f"(от {pre_price_str} до {last_close:.2f} ₽){intraday_ohlc_line}\n"
        f"Volume ratio: {vol_ratio:.1f}x ADV | ADV: {adv_mln:.0f}M ₽"
    )

    # Thesis section
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

    prompt = f"""Ты — трейдер-аналитик. Определи, есть ли спекулятивная возможность.

## Карта решений (прочитай ПЕРЕД анализом данных)

**"Уже в цене?" — матрица:**
| price_move (абс.) | volume > 2× ADV | Вердикт |
|--------------------|-----------------|---------|
| < 2% | — | Окно открыто |
| 2–5% | Нет | Частично в цене |
| 2–5% | Да | В цене → skip (позитив) или ищи перепроданность (негатив) |
| > 5% | — | Сильная реакция → возможна перепроданность/перекупленность |

**4 сценария заработка:**
1. **long-positive**: позитив + price_move < 2% + нет кластера → покупка до реакции
2. **long-oversold**: негатив + price_move > 5% вниз + фундаментал НЕ сломан → покупка на панике
3. **short-negative**: негатив + price_move < 2% + фундаментал сломан → шорт до реакции
4. **short-overbought**: позитив + price_move > 5% вверх + upside < 10% → шорт перекупленности

**Обязательные условия (любое нарушение → skip):**
- risk_reward ≥ 2.0
- ADV ≥ 50M ₽ (для шортов: ADV > 200M)
- Новость не noise (strength ≥ medium)
- Новость ≤ 2 торговых дней
- Тезис не сломан (для long)
- Кластер price_move < 2% (для long-positive)

---

## Компания: {ticker}
Sector: {sector} | Sentiment: {sentiment} | Position: {position}
Fair value: {fair_value} ₽ | Upside: {upside_pct:+.1f}%
{thesis_section}
## Финансовые показатели
{financials_str}

## Дивиденды
{dividends_str}

## Катализаторы
{catalysts_str}

## Новость
{news.get('published_at', news_date)} | {news.get('title', '')}
{news_summary}
Impact: {impact_summary}
Strength: {strength} | URL: {news.get('link', '')}

## Движение цены
{price_section}

{price_table}{orderbook_section}
{intraday_section}
{snapshots_section}
{market_section}{sector_section}{cluster_section}{signals_section}

---
<appendix>
{guide}
</appendix>
---

## Задание
Сначала проведи пошаговый анализ в блоке <analysis>, затем выведи JSON.

<analysis>
Шаг 1. Классификация: тип новости (results/dividends/regulation/corporate/macro/noise), сила, направление
Шаг 2. "Уже в цене?": price_move + volume_ratio → вердикт по матрице выше. Если есть кластер — используй накопленный price_move
Шаг 3. Фундаментал: новость ломает тезис? Усиливает? Временная? Шум?
Шаг 4. Сценарий: какой из 4 сценариев подходит? Если ни один → skip
Шаг 5. Trade setup: entry, target (реалистичный для таймфрейма!), stop-loss (приоритет: сценарий > тип новости), R/R
Шаг 6. Решение: signal + confidence + position_size. Проверь все обязательные условия
</analysis>

Затем выведи JSON trade_signal (только JSON, без обёртки):
{{"date": "YYYY-MM-DD", "trigger": "краткое описание", "trigger_url": "url",
"signal": "buy|sell|skip", "direction": "long-positive|long-oversold|short-negative|short-overbought|skip",
"confidence": "high|medium|low",
"entry": {{"condition": "описание", "price": число}},
"exit": {{"take_profit": число, "stop_loss": число, "time_limit_days": число}},
"expected_return_pct": число, "risk_reward_ratio": число,
"position_size": "full|half|skip", "reasoning": "обоснование"}}"""

    print(prompt)


if __name__ == "__main__":
    main()
