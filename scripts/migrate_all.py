#!/usr/bin/env python3
"""
Migrate all investment-analysis data files into the Investment API.

Usage:
    python3 scripts/migrate_all.py [--api-url URL] [--api-key KEY] [--ticker TICKER]

Environment variables:
    API_URL  - base URL of the Investment API (default: http://localhost:8000)
    API_KEY  - API key for write operations (default: dev-api-key)
"""

import argparse
import csv
import datetime
import io
import json
import os
import re
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("httpx is required: pip install httpx")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPANIES_DIR = PROJECT_ROOT / "companies"
SECTORS_DIR = PROJECT_ROOT / "sectors"


# ---------------------------------------------------------------------------
# YAML frontmatter parser (stdlib only — no PyYAML dependency)
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter between --- delimiters. Simple key-value parser."""
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    raw = match.group(1)
    result = {}
    current_key = None
    current_list = None

    for line in raw.split("\n"):
        # List continuation
        if current_list is not None and re.match(r"^\s+-\s+", line):
            item = re.sub(r"^\s+-\s+", "", line).strip()
            current_list.append(item)
            continue
        elif current_list is not None:
            result[current_key] = current_list
            current_list = None
            current_key = None

        # Key-value pair
        m = re.match(r"^(\w[\w_]*)\s*:\s*(.*)", line)
        if m:
            key = m.group(1)
            value = m.group(2).strip()
            # Check if this starts a list
            if value == "":
                # Might be a list starting on next line — peek handled by loop
                current_key = key
                current_list = []
                continue
            result[key] = _parse_value(value)

    if current_list is not None:
        result[current_key] = current_list

    return result


def _parse_value(s: str) -> object:
    """Parse a scalar YAML value."""
    # Strip surrounding quotes
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        s = s[1:-1]
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if s in ("null", "None", "~"):
        return None
    # Try int
    try:
        return int(s)
    except ValueError:
        pass
    # Try float
    try:
        return float(s)
    except ValueError:
        pass
    return s


# ---------------------------------------------------------------------------
# SmartLab CSV parser
# ---------------------------------------------------------------------------

# Standard metric names → FinancialReport fields
STANDARD_METRICS = {
    "Выручка, млрд руб": "revenue",
    "Чистая прибыль, млрд руб": "net_income",
    "Капитал, млрд руб": "equity",
    "Чистый долг, млрд руб": "net_debt",
    "EPS, руб": "eps",
    "ROE, %": "roe",
    "Див доход, ао, %": "dividend_yield",
}

# Metric names to skip (not useful for reports)
SKIP_METRICS = {
    "Дата отчета",
    "Валюта отчета",
    "Дивиденд, руб/акцию",
    "Дивиденд ап, руб/акцию",
    "Див доход, ап, %",
    "Дивиденды/прибыль, %",
    "Див.выплата, млрд руб",
    "Цена акции ао, руб",
    "Цена акции ап, руб",
    "Число акций ао, млн",
    "Число акций ап, млн",
    "Free Float, %",
    "Капитализация, млрд руб",
    "EV, млрд руб",
    "Персонал, чел",
    "IR рейтинг",
    "Качество фин.отчетности",
    "Презентации для инвесторов",
    "Присутствие на смартлабе",
    "Годовой отчет",
    "Сайт для инвесторов",
    "Календарь инвесторов",
    "Обратная связь",
}


def parse_smartlab_number(s: str) -> float | None:
    """Parse a SmartLab CSV number (Russian locale: comma decimal, space thousands)."""
    if not s or s.strip() == "":
        return None
    s = s.strip().strip('"')
    if not s:
        return None

    # Handle percentage values
    if s.endswith("%"):
        s = s[:-1].strip()
        if not s or s == "":
            return None
        s = s.replace(",", ".").replace("\xa0", "").replace(" ", "")
        try:
            return float(s)
        except ValueError:
            return None

    # Remove thousand separators (spaces, non-breaking spaces)
    s = s.replace("\xa0", "").replace(" ", "")
    # Russian decimal comma → dot
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_smartlab_csv(filepath: Path, period_type: str) -> list[dict]:
    """Parse a SmartLab CSV into a list of FinancialReport payloads."""
    if not filepath.exists():
        return []

    text = filepath.read_text(encoding="utf-8")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    if not rows:
        return []

    # First row is headers: empty + period labels
    periods = rows[0][1:]  # skip first empty cell

    # Build per-period data
    period_data: dict[str, dict] = {}
    for period_label in periods:
        p = period_label.strip()
        if not p:
            continue
        period_data[p] = {"period": p, "standard": {}, "extra": {}}

    # Parse report dates row for later use
    report_dates: dict[str, str | None] = {}
    if len(rows) > 1:
        date_row = rows[1]
        metric_name = date_row[0].strip().strip('"')
        if metric_name == "Дата отчета":
            for i, date_str in enumerate(date_row[1:]):
                if i < len(periods):
                    p = periods[i].strip()
                    if p and date_str.strip():
                        report_dates[p] = date_str.strip()

    # Parse metric rows
    for row in rows[1:]:
        if not row:
            continue
        metric_name = row[0].strip().strip('"')

        if metric_name in SKIP_METRICS or metric_name == "":
            continue

        for i, cell in enumerate(row[1:]):
            if i >= len(periods):
                break
            p = periods[i].strip()
            if not p or p not in period_data:
                continue

            value = parse_smartlab_number(cell)
            if value is None:
                continue

            if metric_name in STANDARD_METRICS:
                field = STANDARD_METRICS[metric_name]
                period_data[p]["standard"][field] = value
            elif metric_name == "P/E" or metric_name == "P/e":
                period_data[p]["standard"]["p_e"] = value
            elif metric_name == "P/B" or metric_name == "P/b":
                period_data[p]["standard"]["p_bv"] = value
            else:
                # Everything else goes to extra_metrics
                period_data[p]["extra"][metric_name] = value

    # Convert to API payloads
    results = []
    for p, data in period_data.items():
        if not data["standard"] and not data["extra"]:
            continue

        # Determine period_type
        if p == "LTM":
            pt = "ltm"
        elif period_type == "yearly":
            pt = "yearly"
        else:
            pt = "quarterly"

        payload = {
            "period": p,
            "period_type": pt,
        }

        # Parse report_date
        if p in report_dates:
            try:
                d = datetime.datetime.strptime(report_dates[p], "%d.%m.%Y").date()
                payload["report_date"] = d.isoformat()
            except ValueError:
                pass

        # Standard fields
        for field, value in data["standard"].items():
            payload[field] = value

        # Extra metrics
        if data["extra"]:
            payload["extra_metrics"] = data["extra"]

        results.append(payload)

    return results


# ---------------------------------------------------------------------------
# Data file parsers
# ---------------------------------------------------------------------------

def parse_company_frontmatter(ticker_dir: Path) -> dict | None:
    """Parse _index.md YAML frontmatter into a CompanyCreate payload."""
    index_file = ticker_dir / "_index.md"
    if not index_file.exists():
        return None

    text = index_file.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)

    if not fm.get("ticker") or fm.get("type") != "company":
        return None
    if fm.get("ticker") == "TICKER" or fm.get("sector") == "sector_name":
        return None  # skip template

    # Parse numeric values that may have text suffixes
    def to_decimal(v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return v
        s = str(v).strip().rstrip("%").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None

    payload = {
        "ticker": fm["ticker"],
        "name": fm.get("name", fm["ticker"]),
        "subsector": fm.get("subsector"),
        "sentiment": fm.get("sentiment"),
        "position": fm.get("position"),
        "my_fair_value": to_decimal(fm.get("my_fair_value")),
        "current_price": to_decimal(fm.get("current_price")),
        "upside": to_decimal(fm.get("upside")),
        "market_cap": to_decimal(fm.get("market_cap_rub")),
        "shares_out": to_decimal(fm.get("shares_outstanding")),
        "free_float": to_decimal(fm.get("free_float")),
        "adv_rub_mln": to_decimal(fm.get("adv_rub_mln")),
        "p_e": to_decimal(fm.get("p_e")),
        "p_bv": to_decimal(fm.get("p_bv")),
        "dividend_yield": to_decimal(fm.get("dividend_yield")),
        "roe": to_decimal(fm.get("roe")),
        "gov_ownership": to_decimal(fm.get("gov_ownership")),
    }

    # Remove None values
    return {k: v for k, v in payload.items() if v is not None}


def parse_catalysts(ticker_dir: Path) -> list[dict]:
    """Parse catalysts.json into CatalystCreate payloads."""
    filepath = ticker_dir / "data" / "catalysts.json"
    if not filepath.exists():
        return []

    data = json.loads(filepath.read_text(encoding="utf-8"))
    catalysts_list = data.get("catalysts", [])

    results = []
    for c in catalysts_list:
        payload = {
            "type": c["type"],
            "impact": c["impact"],
            "magnitude": c.get("magnitude", "medium"),
            "description": c["description"],
            "source": c.get("source"),
            "is_active": True,
        }
        if c.get("date"):
            payload["date"] = c["date"]
        results.append(payload)

    return results


def parse_prices(ticker_dir: Path) -> list[dict]:
    """Parse price_history.csv into PriceCreate payloads."""
    filepath = ticker_dir / "data" / "price_history.csv"
    if not filepath.exists():
        return []

    text = filepath.read_text(encoding="utf-8")
    reader = csv.DictReader(io.StringIO(text))

    results = []
    for row in reader:
        date_str = row.get("date", "").strip()
        close_str = row.get("close", "").strip()
        if not date_str or not close_str:
            continue

        payload = {"date": date_str}

        for field in ("open", "high", "low", "close", "volume_rub"):
            val = row.get(field, "").strip()
            if val:
                try:
                    payload[field] = float(val)
                except ValueError:
                    pass

        # market_cap_bln → market_cap (convert bln to raw)
        mc = row.get("market_cap_bln", "").strip()
        if mc:
            try:
                payload["market_cap"] = float(mc)
            except ValueError:
                pass

        if "close" in payload:
            results.append(payload)

    return results


def parse_dividends(ticker_dir: Path) -> list[dict]:
    """Parse moex_events.json dividends into DividendCreate payloads."""
    filepath = ticker_dir / "data" / "moex_events.json"
    if not filepath.exists():
        return []

    data = json.loads(filepath.read_text(encoding="utf-8"))
    dividends = data.get("dividends", [])

    results = []
    for d in dividends:
        record_date = d.get("registryclosedate")
        amount = d.get("value")
        if not record_date or amount is None:
            continue

        payload = {
            "record_date": record_date,
            "amount": float(amount),
            "currency": d.get("currencyid", "RUB"),
            "status": "paid",  # historical dividends are already paid
        }
        results.append(payload)

    return results


# Confidence mapping: text → numeric
CONFIDENCE_MAP = {"low": 25, "medium": 50, "high": 75}

# Action values not in API ActionEnum
VALID_ACTIONS = {"buy", "hold", "sell"}


def parse_news(ticker_dir: Path) -> list[dict]:
    """Parse news.json into NewsCreate payloads."""
    filepath = ticker_dir / "data" / "news.json"
    if not filepath.exists():
        return []

    data = json.loads(filepath.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []

    results = []
    for item in data:
        date_str = item.get("date", "").strip()
        title = item.get("title", "").strip()
        if not date_str or not title:
            continue

        # Validate date
        try:
            datetime.date.fromisoformat(date_str)
        except ValueError:
            continue

        payload = {
            "date": date_str,
            "title": title[:500],  # truncate very long titles
            "url": item.get("url") or None,
            "source": item.get("source") or None,
            "summary": item.get("summary") or None,
        }

        # Impact enum
        impact = item.get("impact")
        if impact in ("positive", "negative", "mixed", "neutral"):
            payload["impact"] = impact

        # Strength enum
        strength = item.get("strength")
        if strength in ("high", "medium", "low"):
            payload["strength"] = strength

        # Action enum — only valid values
        action = item.get("action")
        if action in VALID_ACTIONS:
            payload["action"] = action

        results.append(payload)

    return results


def parse_trade_signals(ticker_dir: Path) -> list[dict]:
    """Parse trade_signals.json into TradeSignalCreate payloads."""
    filepath = ticker_dir / "data" / "trade_signals.json"
    if not filepath.exists():
        return []

    data = json.loads(filepath.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []

    results = []
    for item in data:
        date_str = item.get("date", "").strip()
        signal = item.get("signal")
        direction = item.get("direction")
        if not date_str or not signal or not direction:
            continue

        # Validate date
        try:
            datetime.date.fromisoformat(date_str)
        except ValueError:
            continue

        # Validate signal enum
        if signal not in ("buy", "skip"):
            continue

        # Validate direction enum
        if direction not in ("long-positive", "long-oversold", "long_positive", "long_oversold", "skip"):
            continue
        # Normalize hyphens to underscores for DB enum compatibility
        direction = direction.replace("-", "_")

        # Map confidence text → numeric
        confidence_raw = item.get("confidence")
        if isinstance(confidence_raw, str):
            confidence = CONFIDENCE_MAP.get(confidence_raw, 50)
        elif isinstance(confidence_raw, (int, float)):
            confidence = confidence_raw
        else:
            confidence = 50

        payload = {
            "date": date_str,
            "signal": signal,
            "direction": direction,
            "confidence": confidence,
            "reasoning": item.get("reasoning"),
        }

        # Position size
        pos_size = item.get("position_size")
        if pos_size in ("full", "half", "skip"):
            payload["position_size"] = pos_size

        # Entry data
        entry = item.get("entry")
        if isinstance(entry, dict):
            if entry.get("price") is not None:
                payload["entry_price"] = float(entry["price"])
            if entry.get("condition"):
                payload["entry_condition"] = entry["condition"]

        # Exit data
        exit_data = item.get("exit")
        if isinstance(exit_data, dict):
            if exit_data.get("take_profit") is not None:
                payload["take_profit"] = float(exit_data["take_profit"])
            if exit_data.get("stop_loss") is not None:
                payload["stop_loss"] = float(exit_data["stop_loss"])
            if exit_data.get("time_limit_days") is not None:
                payload["time_limit_days"] = int(exit_data["time_limit_days"])

        # Other fields
        if item.get("expected_return_pct") is not None:
            payload["expected_return_pct"] = float(item["expected_return_pct"])
        if item.get("risk_reward_ratio") is not None:
            payload["risk_reward"] = float(item["risk_reward_ratio"])

        results.append(payload)

    return results


# ---------------------------------------------------------------------------
# Sector discovery
# ---------------------------------------------------------------------------

def discover_sectors() -> dict[str, str]:
    """Read sector slug → name mapping from sectors/ directory."""
    mapping = {}
    if not SECTORS_DIR.exists():
        return mapping

    for entry in SECTORS_DIR.iterdir():
        if not entry.is_dir():
            continue
        if entry.name.startswith("_"):
            continue
        index_file = entry / "_index.md"
        if index_file.exists():
            text = index_file.read_text(encoding="utf-8")
            fm = parse_frontmatter(text)
            name = fm.get("name", entry.name)
            mapping[entry.name] = name
        else:
            mapping[entry.name] = entry.name

    return mapping


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

class MigrationClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {"X-API-Key": api_key}
        self.client = httpx.Client(timeout=30)
        self.stats = {
            "sectors": {"ok": 0, "err": 0},
            "companies": {"ok": 0, "err": 0},
            "catalysts": {"ok": 0, "err": 0},
            "prices": {"ok": 0, "err": 0},
            "dividends": {"ok": 0, "err": 0},
            "reports": {"ok": 0, "err": 0},
            "news": {"ok": 0, "err": 0},
            "signals": {"ok": 0, "err": 0},
        }
        self.errors: list[str] = []
        # sector slug → id
        self.sector_ids: dict[str, int] = {}
        # ticker → company id
        self.company_ids: dict[str, int] = {}

    def _post(self, path: str, payload: dict) -> httpx.Response | None:
        url = f"{self.base_url}{path}"
        try:
            resp = self.client.post(url, json=payload, headers=self.headers)
            return resp
        except httpx.HTTPError as e:
            self.errors.append(f"HTTP error {path}: {e}")
            return None

    def _get(self, path: str) -> httpx.Response | None:
        url = f"{self.base_url}{path}"
        try:
            return self.client.get(url)
        except httpx.HTTPError as e:
            self.errors.append(f"HTTP error GET {path}: {e}")
            return None

    def create_sectors(self, sector_mapping: dict[str, str]):
        """Create all sectors and store their IDs."""
        print(f"  Creating {len(sector_mapping)} sectors...")
        for slug, name in sorted(sector_mapping.items()):
            resp = self._post("/sectors", {"slug": slug, "name": name})
            if resp and resp.status_code in (200, 201):
                self.sector_ids[slug] = resp.json()["id"]
                self.stats["sectors"]["ok"] += 1
            elif resp and resp.status_code == 409:
                # Already exists — try to get it
                get_resp = self._get(f"/sectors/{slug}")
                if get_resp and get_resp.status_code == 200:
                    self.sector_ids[slug] = get_resp.json()["id"]
                    self.stats["sectors"]["ok"] += 1
                else:
                    self.stats["sectors"]["err"] += 1
                    self.errors.append(f"Sector {slug}: conflict and cannot fetch")
            else:
                self.stats["sectors"]["err"] += 1
                detail = resp.text[:200] if resp else "no response"
                self.errors.append(f"Sector {slug}: {resp.status_code if resp else 'N/A'} — {detail}")

    def create_company(self, ticker: str, payload: dict):
        """Create or update a company."""
        # Resolve sector_id from slug
        sector_slug = None
        # Find sector slug from the original YAML data
        ticker_dir = COMPANIES_DIR / ticker
        index_file = ticker_dir / "_index.md"
        if index_file.exists():
            fm = parse_frontmatter(index_file.read_text(encoding="utf-8"))
            sector_slug = fm.get("sector")
            if sector_slug:
                sector_slug = sector_slug.lower()
                sid = self.sector_ids.get(sector_slug)
                if sid:
                    payload["sector_id"] = sid

        resp = self._post(f"/companies/{ticker}", payload)
        if resp and resp.status_code in (200, 201):
            self.company_ids[ticker] = resp.json()["id"]
            self.stats["companies"]["ok"] += 1
        else:
            self.stats["companies"]["err"] += 1
            detail = resp.text[:200] if resp else "no response"
            self.errors.append(f"Company {ticker}: {resp.status_code if resp else 'N/A'} — {detail}")

    def create_catalysts(self, ticker: str, payloads: list[dict]):
        """Create catalysts for a company."""
        for payload in payloads:
            resp = self._post(f"/companies/{ticker}/catalysts", payload)
            if resp and resp.status_code in (200, 201):
                self.stats["catalysts"]["ok"] += 1
            else:
                self.stats["catalysts"]["err"] += 1
                detail = resp.text[:200] if resp else "no response"
                self.errors.append(f"Catalyst {ticker}: {resp.status_code if resp else 'N/A'} — {detail}")

    def create_prices(self, ticker: str, payloads: list[dict]):
        """Bulk create prices for a company."""
        if not payloads:
            return
        # Send in batches of 500
        batch_size = 500
        for i in range(0, len(payloads), batch_size):
            batch = payloads[i : i + batch_size]
            resp = self._post(f"/companies/{ticker}/prices", {"prices": batch})
            if resp and resp.status_code in (200, 201):
                self.stats["prices"]["ok"] += len(batch)
            else:
                self.stats["prices"]["err"] += len(batch)
                detail = resp.text[:200] if resp else "no response"
                self.errors.append(f"Prices {ticker} batch {i}: {resp.status_code if resp else 'N/A'} — {detail}")

    def create_dividends(self, ticker: str, payloads: list[dict]):
        """Create dividends for a company."""
        for payload in payloads:
            resp = self._post(f"/companies/{ticker}/dividends", payload)
            if resp and resp.status_code in (200, 201):
                self.stats["dividends"]["ok"] += 1
            else:
                self.stats["dividends"]["err"] += 1
                detail = resp.text[:200] if resp else "no response"
                self.errors.append(f"Dividend {ticker}: {resp.status_code if resp else 'N/A'} — {detail}")

    def create_reports(self, ticker: str, payloads: list[dict]):
        """Create financial reports for a company."""
        for payload in payloads:
            resp = self._post(f"/companies/{ticker}/reports", payload)
            if resp and resp.status_code in (200, 201):
                self.stats["reports"]["ok"] += 1
            else:
                self.stats["reports"]["err"] += 1
                detail = resp.text[:200] if resp else "no response"
                self.errors.append(f"Report {ticker} {payload.get('period')}: {resp.status_code if resp else 'N/A'} — {detail}")

    def create_news(self, ticker: str, payloads: list[dict]):
        """Create news for a company."""
        company_id = self.company_ids.get(ticker)
        for payload in payloads:
            if company_id:
                payload["company_id"] = company_id
            resp = self._post("/news", payload)
            if resp and resp.status_code in (200, 201):
                self.stats["news"]["ok"] += 1
            else:
                self.stats["news"]["err"] += 1
                detail = resp.text[:200] if resp else "no response"
                self.errors.append(f"News {ticker}: {resp.status_code if resp else 'N/A'} — {detail}")

    def create_signals(self, ticker: str, payloads: list[dict]):
        """Create trade signals for a company."""
        for payload in payloads:
            resp = self._post(f"/companies/{ticker}/signals", payload)
            if resp and resp.status_code in (200, 201):
                self.stats["signals"]["ok"] += 1
            else:
                self.stats["signals"]["err"] += 1
                detail = resp.text[:200] if resp else "no response"
                self.errors.append(f"Signal {ticker}: {resp.status_code if resp else 'N/A'} — {detail}")

    def print_report(self):
        """Print migration summary."""
        print("\n" + "=" * 60)
        print("Migration Report")
        print("=" * 60)
        total_ok = 0
        total_err = 0
        for entity, counts in self.stats.items():
            ok = counts["ok"]
            err = counts["err"]
            total_ok += ok
            total_err += err
            status = "OK" if err == 0 else "ERRORS"
            print(f"  {entity:15s}: {ok:6d} ok, {err:4d} errors  [{status}]")
        print(f"  {'TOTAL':15s}: {total_ok:6d} ok, {total_err:4d} errors")

        if self.errors:
            print(f"\nFirst {min(20, len(self.errors))} errors:")
            for err in self.errors[:20]:
                print(f"  - {err}")
            if len(self.errors) > 20:
                print(f"  ... and {len(self.errors) - 20} more errors")

    def close(self):
        self.client.close()


# ---------------------------------------------------------------------------
# Main migration logic
# ---------------------------------------------------------------------------

def discover_companies() -> list[str]:
    """List all company tickers (directory names) excluding templates."""
    tickers = []
    for entry in sorted(COMPANIES_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("_"):
            continue
        tickers.append(entry.name)
    return tickers


def migrate_company(client: MigrationClient, ticker: str):
    """Migrate all data for a single company."""
    ticker_dir = COMPANIES_DIR / ticker

    # 1. Company from frontmatter
    payload = parse_company_frontmatter(ticker_dir)
    if not payload:
        print(f"  [{ticker}] Skipping — no valid frontmatter")
        return

    client.create_company(ticker, payload)

    # 2. Catalysts
    catalysts = parse_catalysts(ticker_dir)
    if catalysts:
        client.create_catalysts(ticker, catalysts)

    # 3. Prices
    prices = parse_prices(ticker_dir)
    if prices:
        client.create_prices(ticker, prices)

    # 4. Dividends
    dividends = parse_dividends(ticker_dir)
    if dividends:
        client.create_dividends(ticker, dividends)

    # 5. Financial reports (yearly + quarterly)
    yearly_reports = parse_smartlab_csv(
        ticker_dir / "data" / "smartlab_yearly.csv", "yearly"
    )
    quarterly_reports = parse_smartlab_csv(
        ticker_dir / "data" / "smartlab_quarterly.csv", "quarterly"
    )
    all_reports = yearly_reports + quarterly_reports
    if all_reports:
        client.create_reports(ticker, all_reports)

    # 6. News
    news = parse_news(ticker_dir)
    if news:
        client.create_news(ticker, news)

    # 7. Trade signals
    signals = parse_trade_signals(ticker_dir)
    if signals:
        client.create_signals(ticker, signals)


def main():
    parser = argparse.ArgumentParser(description="Migrate investment-analysis data to API")
    parser.add_argument("--api-url", default=os.environ.get("API_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.environ.get("API_KEY", "dev-api-key"))
    parser.add_argument("--ticker", help="Migrate only a specific ticker")
    args = parser.parse_args()

    print(f"Migrating data to {args.api_url}")

    client = MigrationClient(args.api_url, args.api_key)

    try:
        # Step 1: Create sectors
        sector_mapping = discover_sectors()
        client.create_sectors(sector_mapping)

        # Step 2: Migrate companies
        if args.ticker:
            tickers = [args.ticker]
        else:
            tickers = discover_companies()

        print(f"\nMigrating {len(tickers)} companies...")
        for ticker in tickers:
            print(f"  [{ticker}]")
            migrate_company(client, ticker)

        # Step 3: Report
        client.print_report()

    finally:
        client.close()


if __name__ == "__main__":
    main()
