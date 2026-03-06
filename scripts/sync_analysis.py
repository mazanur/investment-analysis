#!/usr/bin/env python3
"""
Sync analysis data from _index.md into the Investment API.

Parses YAML frontmatter, catalysts, news, and trade signals from
the investment-analysis workspace and pushes them to the API.

Usage:
    python3 scripts/sync_analysis.py SBER
    python3 scripts/sync_analysis.py --all
    python3 scripts/sync_analysis.py SBER --api-url http://localhost:8000

Environment variables:
    API_URL  - base URL of the Investment API (default: http://localhost:8000)
    API_KEY  - API key for write operations (default: dev-api-key)
"""

import argparse
import datetime
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
# YAML frontmatter parser (shared with migrate_all.py)
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter between --- delimiters."""
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    raw = match.group(1)
    result = {}
    current_key = None
    current_list = None

    for line in raw.split("\n"):
        if current_list is not None and re.match(r"^\s+-\s+", line):
            item = re.sub(r"^\s+-\s+", "", line).strip()
            current_list.append(item)
            continue
        elif current_list is not None:
            result[current_key] = current_list
            current_list = None
            current_key = None

        m = re.match(r"^(\w[\w_]*)\s*:\s*(.*)", line)
        if m:
            key = m.group(1)
            value = m.group(2).strip()
            if value == "":
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
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

def to_decimal(v):
    """Convert a value that may have text suffixes (%, млрд) to float."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip().rstrip("%").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


# Confidence mapping: text -> numeric
CONFIDENCE_MAP = {"low": 25, "medium": 50, "high": 75}

# Valid action enum values
VALID_ACTIONS = {"buy", "hold", "sell"}


# ---------------------------------------------------------------------------
# Data parsers
# ---------------------------------------------------------------------------

def parse_company_frontmatter(ticker_dir: Path) -> dict | None:
    """Parse _index.md YAML frontmatter into a CompanyUpdate payload."""
    index_file = ticker_dir / "_index.md"
    if not index_file.exists():
        return None

    text = index_file.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)

    if not fm.get("ticker") or fm.get("type") != "company":
        return None
    if fm.get("ticker") == "TICKER" or fm.get("sector") == "sector_name":
        return None

    payload = {
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

    return {k: v for k, v in payload.items() if v is not None}


def extract_catalysts_from_frontmatter(ticker_dir: Path) -> list[dict]:
    """Extract catalysts from key_risks and key_opportunities in _index.md."""
    index_file = ticker_dir / "_index.md"
    if not index_file.exists():
        return []

    text = index_file.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)

    catalysts = []

    for opp in fm.get("key_opportunities", []):
        catalysts.append({
            "type": "opportunity",
            "impact": "positive",
            "magnitude": "medium",
            "description": opp,
            "source": "index",
            "is_active": True,
        })

    for risk in fm.get("key_risks", []):
        catalysts.append({
            "type": "risk",
            "impact": "negative",
            "magnitude": "medium",
            "description": risk,
            "source": "index",
            "is_active": True,
        })

    return catalysts


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

        try:
            datetime.date.fromisoformat(date_str)
        except ValueError:
            continue

        payload = {
            "date": date_str,
            "title": title[:500],
            "url": item.get("url") or None,
            "source": item.get("source") or None,
            "summary": item.get("summary") or None,
        }

        impact = item.get("impact")
        if impact in ("positive", "negative", "mixed", "neutral"):
            payload["impact"] = impact

        strength = item.get("strength")
        if strength in ("high", "medium", "low"):
            payload["strength"] = strength

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

        try:
            datetime.date.fromisoformat(date_str)
        except ValueError:
            continue

        if signal not in ("buy", "skip"):
            continue
        if direction not in ("long-positive", "long-oversold", "long_positive", "long_oversold", "skip"):
            continue
        # Normalize hyphens to underscores for DB enum compatibility
        direction = direction.replace("-", "_")

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

        pos_size = item.get("position_size")
        if pos_size in ("full", "half", "skip"):
            payload["position_size"] = pos_size

        entry = item.get("entry")
        if isinstance(entry, dict):
            if entry.get("price") is not None:
                payload["entry_price"] = float(entry["price"])
            if entry.get("condition"):
                payload["entry_condition"] = entry["condition"]

        exit_data = item.get("exit")
        if isinstance(exit_data, dict):
            if exit_data.get("take_profit") is not None:
                payload["take_profit"] = float(exit_data["take_profit"])
            if exit_data.get("stop_loss") is not None:
                payload["stop_loss"] = float(exit_data["stop_loss"])
            if exit_data.get("time_limit_days") is not None:
                payload["time_limit_days"] = int(exit_data["time_limit_days"])

        if item.get("expected_return_pct") is not None:
            payload["expected_return_pct"] = float(item["expected_return_pct"])
        if item.get("risk_reward_ratio") is not None:
            payload["risk_reward"] = float(item["risk_reward_ratio"])

        results.append(payload)

    return results


# ---------------------------------------------------------------------------
# Sync client
# ---------------------------------------------------------------------------

class SyncClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {"X-API-Key": api_key}
        self.client = httpx.Client(timeout=30)
        self.stats = {
            "companies": {"ok": 0, "err": 0},
            "catalysts_deactivated": {"ok": 0, "err": 0},
            "catalysts_created": {"ok": 0, "err": 0},
            "news": {"ok": 0, "err": 0},
            "signals": {"ok": 0, "err": 0},
        }
        self.errors: list[str] = []

    def _put(self, path: str, payload: dict) -> httpx.Response | None:
        url = f"{self.base_url}{path}"
        try:
            return self.client.put(url, json=payload, headers=self.headers)
        except httpx.HTTPError as e:
            self.errors.append(f"HTTP error PUT {path}: {e}")
            return None

    def _post(self, path: str, payload: dict) -> httpx.Response | None:
        url = f"{self.base_url}{path}"
        try:
            return self.client.post(url, json=payload, headers=self.headers)
        except httpx.HTTPError as e:
            self.errors.append(f"HTTP error POST {path}: {e}")
            return None

    def _get(self, path: str, params: dict | None = None) -> httpx.Response | None:
        url = f"{self.base_url}{path}"
        try:
            return self.client.get(url, params=params)
        except httpx.HTTPError as e:
            self.errors.append(f"HTTP error GET {path}: {e}")
            return None

    def get_company_id(self, ticker: str) -> int | None:
        """Fetch company_id from the API by ticker."""
        resp = self._get(f"/companies/{ticker}")
        if resp and resp.status_code == 200:
            return resp.json().get("id")
        return None

    def update_company(self, ticker: str, payload: dict) -> bool:
        """Update company data via PUT /companies/{ticker}."""
        # Resolve sector slug to sector_id
        ticker_dir = COMPANIES_DIR / ticker
        index_file = ticker_dir / "_index.md"
        if index_file.exists():
            fm = parse_frontmatter(index_file.read_text(encoding="utf-8"))
            sector_slug = fm.get("sector")
            if sector_slug:
                slug = sector_slug.lower()
                sector_resp = self._get(f"/sectors/{slug}")
                if sector_resp and sector_resp.status_code == 200:
                    payload["sector_id"] = sector_resp.json()["id"]
                elif sector_resp and sector_resp.status_code == 404:
                    # Auto-create the sector
                    create_resp = self._post(
                        "/sectors",
                        {"slug": slug, "name": sector_slug.replace("-", " ").title()},
                    )
                    if create_resp and create_resp.status_code in (200, 201):
                        payload["sector_id"] = create_resp.json()["id"]

        resp = self._put(f"/companies/{ticker}", payload)
        if resp and resp.status_code == 200:
            self.stats["companies"]["ok"] += 1
            return True

        # Company may not exist yet — try POST (upsert)
        if resp and resp.status_code == 404:
            payload["ticker"] = ticker
            resp = self._post(f"/companies/{ticker}", payload)
            if resp and resp.status_code in (200, 201):
                self.stats["companies"]["ok"] += 1
                return True

        self.stats["companies"]["err"] += 1
        detail = resp.text[:200] if resp else "no response"
        self.errors.append(
            f"Company {ticker}: {resp.status_code if resp else 'N/A'} — {detail}"
        )
        return False

    def sync_catalysts(self, ticker: str, new_catalysts: list[dict]):
        """Deactivate old catalysts from 'index' source, then create new ones."""
        # Get existing active catalysts
        resp = self._get(f"/companies/{ticker}/catalysts", params={"is_active": "true"})
        if resp and resp.status_code == 200:
            existing = resp.json()
            # Deactivate old catalysts that came from _index.md
            for cat in existing:
                if cat.get("source") == "index":
                    deact_resp = self._put(
                        f"/catalysts/{cat['id']}", {"is_active": False}
                    )
                    if deact_resp and deact_resp.status_code == 200:
                        self.stats["catalysts_deactivated"]["ok"] += 1
                    else:
                        self.stats["catalysts_deactivated"]["err"] += 1

        # Create new catalysts
        for payload in new_catalysts:
            resp = self._post(f"/companies/{ticker}/catalysts", payload)
            if resp and resp.status_code in (200, 201):
                self.stats["catalysts_created"]["ok"] += 1
            else:
                self.stats["catalysts_created"]["err"] += 1
                detail = resp.text[:200] if resp else "no response"
                self.errors.append(
                    f"Catalyst {ticker}: {resp.status_code if resp else 'N/A'} — {detail}"
                )

    def sync_news(self, ticker: str, news_payloads: list[dict]):
        """Sync news — get existing news titles to avoid duplicates."""
        company_id = self.get_company_id(ticker)
        if not company_id:
            self.errors.append(f"News {ticker}: company not found in API")
            return

        # Get existing news for this company to check for duplicates
        resp = self._get(f"/companies/{ticker}/news")
        existing_keys = set()
        if resp and resp.status_code == 200:
            for n in resp.json():
                existing_keys.add((n.get("date"), n.get("title")))

        for payload in news_payloads:
            key = (payload.get("date"), payload.get("title"))
            if key in existing_keys:
                continue
            payload["company_id"] = company_id
            resp = self._post("/news", payload)
            if resp and resp.status_code in (200, 201):
                self.stats["news"]["ok"] += 1
            else:
                self.stats["news"]["err"] += 1
                detail = resp.text[:200] if resp else "no response"
                self.errors.append(
                    f"News {ticker}: {resp.status_code if resp else 'N/A'} — {detail}"
                )

    def sync_signals(self, ticker: str, signal_payloads: list[dict]):
        """Sync trade signals — check for duplicates by (date, signal, direction)."""
        resp = self._get(f"/companies/{ticker}/signals")
        existing_keys = set()
        if resp and resp.status_code == 200:
            for s in resp.json():
                key = (s.get("date"), s.get("signal"), s.get("direction"))
                existing_keys.add(key)

        for payload in signal_payloads:
            key = (payload.get("date"), payload.get("signal"), payload.get("direction"))
            if key in existing_keys:
                continue
            resp = self._post(f"/companies/{ticker}/signals", payload)
            if resp and resp.status_code in (200, 201):
                self.stats["signals"]["ok"] += 1
            else:
                self.stats["signals"]["err"] += 1
                detail = resp.text[:200] if resp else "no response"
                self.errors.append(
                    f"Signal {ticker}: {resp.status_code if resp else 'N/A'} — {detail}"
                )

    def print_report(self):
        """Print sync summary."""
        print("\n" + "=" * 60)
        print("Sync Report")
        print("=" * 60)
        total_ok = 0
        total_err = 0
        for entity, counts in self.stats.items():
            ok = counts["ok"]
            err = counts["err"]
            total_ok += ok
            total_err += err
            status = "OK" if err == 0 else "ERRORS"
            print(f"  {entity:25s}: {ok:4d} ok, {err:4d} errors  [{status}]")
        print(f"  {'TOTAL':25s}: {total_ok:4d} ok, {total_err:4d} errors")

        if self.errors:
            print(f"\nFirst {min(20, len(self.errors))} errors:")
            for err in self.errors[:20]:
                print(f"  - {err}")
            if len(self.errors) > 20:
                print(f"  ... and {len(self.errors) - 20} more errors")

    def close(self):
        self.client.close()


# ---------------------------------------------------------------------------
# Sync logic
# ---------------------------------------------------------------------------

def discover_companies() -> list[str]:
    """List all company tickers excluding templates."""
    tickers = []
    for entry in sorted(COMPANIES_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("_"):
            continue
        tickers.append(entry.name)
    return tickers


def sync_ticker(client: SyncClient, ticker: str):
    """Sync all data for a single company."""
    ticker_dir = COMPANIES_DIR / ticker

    # 1. Update company from frontmatter
    payload = parse_company_frontmatter(ticker_dir)
    if not payload:
        print(f"  [{ticker}] Skipping — no valid frontmatter")
        return

    client.update_company(ticker, payload)

    # 2. Sync catalysts: deactivate old index-sourced, create new from frontmatter
    catalysts = extract_catalysts_from_frontmatter(ticker_dir)
    client.sync_catalysts(ticker, catalysts)

    # 3. Sync news (new entries only)
    news = parse_news(ticker_dir)
    if news:
        client.sync_news(ticker, news)

    # 4. Sync trade signals (new entries only)
    signals = parse_trade_signals(ticker_dir)
    if signals:
        client.sync_signals(ticker, signals)


def main():
    parser = argparse.ArgumentParser(
        description="Sync analysis data from _index.md into the Investment API"
    )
    parser.add_argument("ticker", nargs="?", help="Ticker to sync (e.g., SBER)")
    parser.add_argument(
        "--all", action="store_true", help="Sync all companies"
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("API_URL", "http://localhost:8000"),
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("API_KEY", "dev-api-key"),
    )
    args = parser.parse_args()

    if not args.ticker and not args.all:
        parser.error("Provide a ticker or use --all")

    if args.all:
        tickers = discover_companies()
    else:
        tickers = [args.ticker]

    print(f"Syncing {len(tickers)} company(ies) to {args.api_url}")

    client = SyncClient(args.api_url, args.api_key)
    try:
        for ticker in tickers:
            print(f"  [{ticker}]")
            sync_ticker(client, ticker)
        client.print_report()
    finally:
        client.close()


if __name__ == "__main__":
    main()
