"""
Tests for migrate_all.py — verify parsing of all data file formats into correct API payloads.
Uses real SBER data files from the companies/ directory as test fixtures.
"""

import json
import sys
from pathlib import Path

import pytest

# Add scripts/ to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from migrate_all import (
    CONFIDENCE_MAP,
    discover_companies,
    discover_sectors,
    parse_catalysts,
    parse_company_frontmatter,
    parse_dividends,
    parse_frontmatter,
    parse_news,
    parse_prices,
    parse_smartlab_csv,
    parse_smartlab_number,
    parse_trade_signals,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SBER_DIR = PROJECT_ROOT / "companies" / "SBER"


# ---------------------------------------------------------------------------
# YAML frontmatter parsing
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_basic_parsing(self):
        text = """---
type: company
ticker: SBER
name: Сбербанк
sector: finance
sentiment: bullish
position: buy
my_fair_value: 520
current_price: 314.68
upside: 63
---

# Content here
"""
        fm = parse_frontmatter(text)
        assert fm["type"] == "company"
        assert fm["ticker"] == "SBER"
        assert fm["name"] == "Сбербанк"
        assert fm["sector"] == "finance"
        assert fm["sentiment"] == "bullish"
        assert fm["position"] == "buy"
        assert fm["my_fair_value"] == 520
        assert fm["current_price"] == 314.68
        assert fm["upside"] == 63

    def test_list_parsing(self):
        text = """---
key_risks:
  - Risk one
  - Risk two
key_opportunities:
  - Opportunity one
---
"""
        fm = parse_frontmatter(text)
        assert fm["key_risks"] == ["Risk one", "Risk two"]
        assert fm["key_opportunities"] == ["Opportunity one"]

    def test_no_frontmatter(self):
        text = "# Just a heading\nSome content"
        fm = parse_frontmatter(text)
        assert fm == {}


# ---------------------------------------------------------------------------
# Company frontmatter → API payload
# ---------------------------------------------------------------------------


class TestParseCompanyFrontmatter:
    def test_sber_frontmatter(self):
        payload = parse_company_frontmatter(SBER_DIR)
        assert payload is not None
        assert payload["ticker"] == "SBER"
        assert payload["name"] == "Сбербанк"
        assert payload["sentiment"] == "bullish"
        assert payload["position"] == "buy"
        assert payload["my_fair_value"] == 520.0
        # current_price is a decimal
        assert isinstance(payload["current_price"], float)
        assert payload["upside"] == 63.0
        assert payload["p_e"] == 4.03
        assert payload["gov_ownership"] == 50.0

    def test_template_skipped(self):
        template_dir = PROJECT_ROOT / "companies" / "_TEMPLATE"
        payload = parse_company_frontmatter(template_dir)
        assert payload is None

    def test_nonexistent_dir(self):
        payload = parse_company_frontmatter(Path("/nonexistent"))
        assert payload is None


# ---------------------------------------------------------------------------
# Catalysts
# ---------------------------------------------------------------------------


class TestParseCatalysts:
    def test_sber_catalysts(self):
        catalysts = parse_catalysts(SBER_DIR)
        assert len(catalysts) > 0

        # Check first catalyst structure
        first = catalysts[0]
        assert "type" in first
        assert first["type"] in ("opportunity", "risk", "cb_meeting", "event")
        assert "impact" in first
        assert first["impact"] in ("positive", "negative", "mixed", "neutral")
        assert "magnitude" in first
        assert first["magnitude"] in ("high", "medium", "low")
        assert "description" in first
        assert isinstance(first["description"], str)
        assert first["is_active"] is True

    def test_has_cb_meeting(self):
        catalysts = parse_catalysts(SBER_DIR)
        types = [c["type"] for c in catalysts]
        assert "cb_meeting" in types

    def test_cb_meeting_has_date(self):
        catalysts = parse_catalysts(SBER_DIR)
        cb = [c for c in catalysts if c["type"] == "cb_meeting"]
        assert len(cb) > 0
        assert "date" in cb[0]

    def test_nonexistent_returns_empty(self):
        assert parse_catalysts(Path("/nonexistent")) == []


# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------


class TestParsePrices:
    def test_sber_prices(self):
        prices = parse_prices(SBER_DIR)
        assert len(prices) > 0

        first = prices[0]
        assert "date" in first
        assert "close" in first
        assert isinstance(first["close"], float)

        # Check OHLCV fields
        assert "open" in first
        assert "high" in first
        assert "low" in first
        assert "volume_rub" in first

    def test_date_format(self):
        prices = parse_prices(SBER_DIR)
        # All dates should be YYYY-MM-DD format
        import datetime

        for p in prices[:5]:
            datetime.date.fromisoformat(p["date"])

    def test_nonexistent_returns_empty(self):
        assert parse_prices(Path("/nonexistent")) == []


# ---------------------------------------------------------------------------
# Dividends
# ---------------------------------------------------------------------------


class TestParseDividends:
    def test_sber_dividends(self):
        dividends = parse_dividends(SBER_DIR)
        assert len(dividends) > 0

        first = dividends[0]
        assert "record_date" in first
        assert "amount" in first
        assert isinstance(first["amount"], float)
        assert first["currency"] == "RUB"
        assert first["status"] == "paid"

    def test_nonexistent_returns_empty(self):
        assert parse_dividends(Path("/nonexistent")) == []


# ---------------------------------------------------------------------------
# SmartLab CSV / Financial Reports
# ---------------------------------------------------------------------------


class TestParseSmartlabNumber:
    def test_simple_number(self):
        assert parse_smartlab_number("123.4") == 123.4

    def test_russian_comma(self):
        assert parse_smartlab_number("18,7") == 18.7

    def test_thousands_with_spaces(self):
        assert parse_smartlab_number('"1 104"') == 1104.0

    def test_negative_with_spaces(self):
        assert parse_smartlab_number('"-2 309"') == -2309.0

    def test_percentage(self):
        assert parse_smartlab_number("12.3%") == 12.3

    def test_empty_string(self):
        assert parse_smartlab_number("") is None

    def test_none_value(self):
        assert parse_smartlab_number("   ") is None

    def test_zero(self):
        assert parse_smartlab_number("0") == 0.0

    def test_zero_percent(self):
        assert parse_smartlab_number("0.0%") == 0.0


class TestParseSmartlabCSV:
    def test_sber_yearly(self):
        filepath = SBER_DIR / "data" / "smartlab_yearly.csv"
        reports = parse_smartlab_csv(filepath, "yearly")
        assert len(reports) > 0

        # Find a report with net_income
        reports_with_income = [r for r in reports if "net_income" in r]
        assert len(reports_with_income) > 0

        # Check structure
        sample = reports_with_income[0]
        assert "period" in sample
        assert "period_type" in sample
        assert sample["period_type"] in ("yearly", "ltm")
        assert isinstance(sample["net_income"], float)

    def test_sber_quarterly(self):
        filepath = SBER_DIR / "data" / "smartlab_quarterly.csv"
        reports = parse_smartlab_csv(filepath, "quarterly")
        assert len(reports) > 0

        # Should have quarterly period types
        quarterly = [r for r in reports if r["period_type"] == "quarterly"]
        assert len(quarterly) > 0
        # Quarterly periods should be like "2025Q4"
        assert any("Q" in r["period"] for r in quarterly)

    def test_ltm_period(self):
        filepath = SBER_DIR / "data" / "smartlab_yearly.csv"
        reports = parse_smartlab_csv(filepath, "yearly")
        ltm = [r for r in reports if r["period"] == "LTM"]
        assert len(ltm) == 1
        assert ltm[0]["period_type"] == "ltm"

    def test_extra_metrics(self):
        filepath = SBER_DIR / "data" / "smartlab_yearly.csv"
        reports = parse_smartlab_csv(filepath, "yearly")
        # SBER should have banking-specific metrics in extra_metrics
        reports_with_extra = [r for r in reports if r.get("extra_metrics")]
        assert len(reports_with_extra) > 0

    def test_report_dates_parsed(self):
        filepath = SBER_DIR / "data" / "smartlab_yearly.csv"
        reports = parse_smartlab_csv(filepath, "yearly")
        reports_with_date = [r for r in reports if "report_date" in r]
        assert len(reports_with_date) > 0
        # Report date should be ISO format
        import datetime

        for r in reports_with_date:
            datetime.date.fromisoformat(r["report_date"])

    def test_nonexistent_returns_empty(self):
        assert parse_smartlab_csv(Path("/nonexistent"), "yearly") == []


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------


class TestParseNews:
    def test_sber_news(self):
        news = parse_news(SBER_DIR)
        assert len(news) > 0

        first = news[0]
        assert "date" in first
        assert "title" in first
        assert isinstance(first["title"], str)

    def test_valid_impact_values(self):
        news = parse_news(SBER_DIR)
        valid_impacts = {"positive", "negative", "mixed", "neutral"}
        for item in news:
            if "impact" in item:
                assert item["impact"] in valid_impacts

    def test_valid_action_values(self):
        news = parse_news(SBER_DIR)
        valid_actions = {"buy", "hold", "sell"}
        for item in news:
            if "action" in item:
                assert item["action"] in valid_actions

    def test_skips_empty_dates(self):
        news = parse_news(SBER_DIR)
        for item in news:
            assert item["date"] != ""

    def test_nonexistent_returns_empty(self):
        assert parse_news(Path("/nonexistent")) == []


# ---------------------------------------------------------------------------
# Trade Signals
# ---------------------------------------------------------------------------


class TestParseTradeSignals:
    def test_sber_signals(self):
        signals = parse_trade_signals(SBER_DIR)
        assert len(signals) > 0

        first = signals[0]
        assert "date" in first
        assert "signal" in first
        assert first["signal"] in ("buy", "skip")
        assert "direction" in first
        assert first["direction"] in ("long_positive", "long_oversold", "skip")
        assert "confidence" in first
        assert isinstance(first["confidence"], (int, float))
        assert 0 <= first["confidence"] <= 100

    def test_confidence_mapped(self):
        signals = parse_trade_signals(SBER_DIR)
        # All confidences should be numeric
        for s in signals:
            assert isinstance(s["confidence"], (int, float))

    def test_valid_position_sizes(self):
        signals = parse_trade_signals(SBER_DIR)
        valid_sizes = {"full", "half", "skip"}
        for s in signals:
            if "position_size" in s:
                assert s["position_size"] in valid_sizes

    def test_nonexistent_returns_empty(self):
        assert parse_trade_signals(Path("/nonexistent")) == []


# ---------------------------------------------------------------------------
# Sector discovery
# ---------------------------------------------------------------------------


class TestDiscoverSectors:
    def test_finds_sectors(self):
        sectors = discover_sectors()
        assert len(sectors) > 0
        assert "finance" in sectors
        assert "oil-gas" in sectors

    def test_sector_names(self):
        sectors = discover_sectors()
        assert sectors["finance"] == "Финансы"
        assert sectors["oil-gas"] == "Нефтегаз"

    def test_excludes_templates(self):
        sectors = discover_sectors()
        assert "_TEMPLATE" not in sectors


# ---------------------------------------------------------------------------
# Company discovery
# ---------------------------------------------------------------------------


class TestDiscoverCompanies:
    def test_finds_companies(self):
        tickers = discover_companies()
        assert len(tickers) > 0
        assert "SBER" in tickers

    def test_excludes_templates(self):
        tickers = discover_companies()
        assert "_TEMPLATE" not in tickers


# ---------------------------------------------------------------------------
# Integration: full SBER parse
# ---------------------------------------------------------------------------


class TestSBERFullParse:
    """Test that parsing all SBER data files produces valid API payloads."""

    def test_all_data_types_parsed(self):
        company = parse_company_frontmatter(SBER_DIR)
        catalysts = parse_catalysts(SBER_DIR)
        prices = parse_prices(SBER_DIR)
        dividends = parse_dividends(SBER_DIR)
        yearly = parse_smartlab_csv(SBER_DIR / "data" / "smartlab_yearly.csv", "yearly")
        quarterly = parse_smartlab_csv(SBER_DIR / "data" / "smartlab_quarterly.csv", "quarterly")
        news = parse_news(SBER_DIR)
        signals = parse_trade_signals(SBER_DIR)

        assert company is not None
        assert len(catalysts) > 0
        assert len(prices) > 0
        assert len(dividends) > 0
        assert len(yearly) > 0
        assert len(quarterly) > 0
        assert len(news) > 0
        assert len(signals) > 0

    def test_company_payload_valid_for_api(self):
        """Company payload has all required fields and valid enum values."""
        company = parse_company_frontmatter(SBER_DIR)
        assert "ticker" in company
        assert "name" in company
        # Valid enum values
        assert company["sentiment"] in ("bullish", "neutral", "bearish")
        assert company["position"] in ("buy", "hold", "sell", "watch", "avoid")

    def test_prices_bulk_format(self):
        """Prices should be ready for PriceBulkCreate format."""
        prices = parse_prices(SBER_DIR)
        # Build bulk payload
        bulk = {"prices": prices}
        assert isinstance(bulk["prices"], list)
        assert len(bulk["prices"]) > 0
        for p in bulk["prices"][:5]:
            assert "date" in p
            assert "close" in p

    def test_dividends_have_record_dates(self):
        dividends = parse_dividends(SBER_DIR)
        for d in dividends:
            assert "record_date" in d
            assert "amount" in d
            assert d["amount"] > 0
