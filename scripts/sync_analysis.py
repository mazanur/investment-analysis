#!/usr/bin/env python3
"""
Sync analysis data from _index.md into the Investment API.

Parses YAML frontmatter and catalysts from the investment-analysis
workspace and pushes them to the API.

Usage:
    python3 scripts/sync_analysis.py SBER
    python3 scripts/sync_analysis.py --all
    python3 scripts/sync_analysis.py SBER --api-url http://localhost:8000

Environment variables:
    API_URL  - base URL of the Investment API (default: http://localhost:8000)
    API_KEY  - API key for write operations (default: dev-api-key)
"""

import argparse
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

def _parse_inline_list(s: str) -> list[str]:
    """Parse inline YAML list like [a, b, c]."""
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        return [item.strip().strip("'\"") for item in s[1:-1].split(",") if item.strip()]
    return []


def parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter between --- delimiters.

    Supports both simple lists and structured list items:
      key_risks:
        - Simple string item
        - text: Structured item with sub-fields
          trigger_tags: [tag1, tag2]
    """
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    raw = match.group(1)
    result = {}
    current_key = None
    current_list = None
    current_item = None  # dict for structured list items

    for line in raw.split("\n"):
        # Sub-field of a structured list item (e.g. "    trigger_tags: [...]")
        if current_item is not None:
            sub_m = re.match(r"^\s{4,}(\w+)\s*:\s*(.*)", line)
            if sub_m:
                sub_key = sub_m.group(1)
                sub_val = sub_m.group(2).strip()
                if sub_val.startswith("["):
                    current_item[sub_key] = _parse_inline_list(sub_val)
                else:
                    current_item[sub_key] = _parse_value(sub_val)
                continue
            else:
                current_item = None  # end of sub-fields

        # List item: "  - ..."
        if current_list is not None and re.match(r"^\s+-\s+", line):
            item_text = re.sub(r"^\s+-\s+", "", line).strip()
            # Check if it's a structured item: "- text: ..."
            text_m = re.match(r"^text:\s*(.*)", item_text)
            if text_m:
                current_item = {"text": text_m.group(1).strip()}
                current_list.append(current_item)
            else:
                current_list.append(item_text)
            continue
        elif current_list is not None and not re.match(r"^\s{4,}", line):
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


# ---------------------------------------------------------------------------
# Markdown body extractors
# ---------------------------------------------------------------------------

def extract_business_model(text: str) -> str | None:
    """Extract 'Бизнес-модель' opening paragraph from _index.md (up to 200 chars)."""
    m = re.search(r"## Бизнес-модель\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if not m:
        return None
    body = m.group(1).strip()
    lines = body.split("\n")
    result_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if result_lines:
                break
            continue
        result_lines.append(stripped)
    result = " ".join(result_lines)
    if not result:
        return None
    if len(result) > 200:
        result = result[:197] + "..."
    return result


def extract_thesis(text: str) -> str | None:
    """Extract 'Мой тезис' / 'Инвестиционный тезис' opening paragraph (up to 500 chars)."""
    m = re.search(r"## (?:Мой тезис|Инвестиционный тезис)\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if not m:
        return None
    body = m.group(1).strip()
    lines = body.split("\n")
    result_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if result_lines:
                break
            continue
        if re.match(r"\*\*Обновлени[ея]", stripped):
            continue
        result_lines.append(stripped)
    result = " ".join(result_lines)
    if not result:
        return None
    if len(result) > 500:
        result = result[:497] + "..."
    return result


def extract_scenarios(text: str) -> str | None:
    """Extract fair value scenarios table (pessimistic/base/optimistic).

    Supports two formats:
    1. Row-based: | Пессимистичный (...) | ... | 2500 руб. | -52% |
    2. Column-based: header | Пессимистичный | Базовый | Оптимистичный |
       with price/upside rows below.
    """
    # --- Try row-based format first (scenario name in first column) ---
    # Match scenario names with optional extra text in parentheses and bold markers
    scenarios = []
    seen_names = set()
    for m in re.finditer(
        r"\|\s*\*{0,2}(Пессимистичн\w*|Базов\w*|Оптимистичн\w*)[^|]*\*{0,2}\s*\|(.+)\|",
        text,
    ):
        raw_name = m.group(1).strip()
        # Normalize to short name
        if raw_name.startswith("Пессимистичн"):
            name = "Пессимистичный"
        elif raw_name.startswith("Базов"):
            name = "Базовый"
        else:
            name = "Оптимистичный"
        if name in seen_names:
            break
        seen_names.add(name)
        rest = m.group(2).strip()
        cells = [c.strip().replace("**", "").strip() for c in rest.split("|")]
        upside_idx = None
        for i in range(len(cells) - 1, -1, -1):
            if "%" in cells[i] and re.search(r"[+-]?\d+", cells[i]):
                upside_idx = i
                break
        if upside_idx is not None and upside_idx > 0:
            upside = cells[upside_idx].strip()
            price_raw = cells[upside_idx - 1].strip()
            price = re.sub(r"[^\d.]", "", price_raw.replace(",", "").replace(" ", "")).strip(".")
            if price:
                scenarios.append(f"{name}: {price} ₽ ({upside})")
    if scenarios:
        return " | ".join(scenarios)

    # --- Try column-based format (scenario names as column headers) ---
    # Find header: | ... | Пессимистичный | Базовый | Оптимистичный |
    header_m = re.search(
        r"\|[^|]*\|\s*\*{0,2}Пессимистичн\w*\*{0,2}\s*\|\s*\*{0,2}Базов\w*\*{0,2}\s*\|\s*\*{0,2}Оптимистичн\w*\*{0,2}\s*\|",
        text,
    )
    if not header_m:
        return None

    # Find price and upside rows after the header
    after_header = text[header_m.end():]
    lines = after_header.split("\n")
    price_cells = None
    upside_cells = None
    for line in lines:
        line_clean = line.strip().replace("**", "")
        if not line_clean.startswith("|"):
            continue
        cells = [c.strip() for c in line_clean.strip("|").split("|")]
        if len(cells) < 4:
            continue
        label = cells[0].lower()
        # Price row: contains "целев" (целевая цена) or "цена" and has numbers
        if ("целев" in label or "цена" == label) and re.search(r"\d", cells[1]):
            price_cells = cells[1:4]
        # Upside row
        if "upside" in label and re.search(r"[+-]?\d+%", cells[1]):
            upside_cells = cells[1:4]

    if price_cells:
        names = ["Пессимистичный", "Базовый", "Оптимистичный"]
        for i, name in enumerate(names):
            price = re.sub(r"[^\d.]", "", price_cells[i].replace(",", "").replace(" ", ""))
            if price:
                upside = upside_cells[i].strip() if upside_cells else ""
                if upside:
                    scenarios.append(f"{name}: {price} ₽ ({upside})")
                else:
                    scenarios.append(f"{name}: {price} ₽")

    return " | ".join(scenarios) if scenarios else None


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

    # Extract text sections from markdown body
    business_model = extract_business_model(text)
    thesis = extract_thesis(text)
    scenarios = extract_scenarios(text)

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
        "business_model": business_model,
        "thesis": thesis,
        "scenarios": scenarios,
    }

    return {k: v for k, v in payload.items() if v is not None}


def _extract_item(item) -> tuple[str, list[str] | None]:
    """Extract description and trigger_tags from a list item (str or dict)."""
    if isinstance(item, dict):
        return item.get("text", ""), item.get("trigger_tags")
    return item, None


def extract_catalysts_from_frontmatter(ticker_dir: Path) -> list[dict]:
    """Extract catalysts from key_risks and key_opportunities in _index.md."""
    index_file = ticker_dir / "_index.md"
    if not index_file.exists():
        return []

    text = index_file.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)

    catalysts = []

    for opp in fm.get("key_opportunities", []):
        desc, tags = _extract_item(opp)
        cat = {
            "type": "opportunity",
            "impact": "positive",
            "magnitude": "medium",
            "description": desc,
            "source": "index",
            "is_active": True,
        }
        if tags:
            cat["trigger_tags"] = tags
        catalysts.append(cat)

    for risk in fm.get("key_risks", []):
        desc, tags = _extract_item(risk)
        cat = {
            "type": "risk",
            "impact": "negative",
            "magnitude": "medium",
            "description": desc,
            "source": "index",
            "is_active": True,
        }
        if tags:
            cat["trigger_tags"] = tags
        catalysts.append(cat)

    return catalysts


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
                    try:
                        payload["sector_id"] = sector_resp.json()["id"]
                    except Exception:
                        pass
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
        default=os.environ.get("API_URL", "https://investment-api.zagirnur.dev"),
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
