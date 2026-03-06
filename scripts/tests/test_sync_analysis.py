"""
Tests for sync_analysis.py — verify parsing and payload formation for sync operations.
Uses real SBER data files from the companies/ directory as test fixtures.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock


# Add scripts/ to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sync_analysis import (
    SyncClient,
    discover_companies,
    extract_catalysts_from_frontmatter,
    parse_company_frontmatter,
    parse_frontmatter,
    parse_news,
    parse_trade_signals,
    sync_ticker,
    to_decimal,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SBER_DIR = PROJECT_ROOT / "companies" / "SBER"


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_basic_parsing(self):
        text = """---
type: company
ticker: TEST
name: Test Company
sentiment: bullish
position: buy
my_fair_value: 100
current_price: 80
upside: 25
---

# Content
"""
        fm = parse_frontmatter(text)
        assert fm["ticker"] == "TEST"
        assert fm["sentiment"] == "bullish"
        assert fm["my_fair_value"] == 100
        assert fm["upside"] == 25

    def test_list_parsing(self):
        text = """---
key_risks:
  - Risk one
  - Risk two
key_opportunities:
  - Opp one
---
"""
        fm = parse_frontmatter(text)
        assert fm["key_risks"] == ["Risk one", "Risk two"]
        assert fm["key_opportunities"] == ["Opp one"]

    def test_no_frontmatter(self):
        assert parse_frontmatter("No frontmatter here") == {}


# ---------------------------------------------------------------------------
# Company payload
# ---------------------------------------------------------------------------


class TestParseCompanyFrontmatter:
    def test_sber_returns_valid_payload(self):
        payload = parse_company_frontmatter(SBER_DIR)
        assert payload is not None
        assert "name" in payload
        assert payload["sentiment"] in ("bullish", "neutral", "bearish")
        assert payload["position"] in ("buy", "hold", "sell", "watch", "avoid")
        assert isinstance(payload.get("my_fair_value"), (int, float))
        assert isinstance(payload.get("current_price"), (int, float))

    def test_payload_excludes_ticker(self):
        """CompanyUpdate payload should not include ticker (it's in the URL)."""
        payload = parse_company_frontmatter(SBER_DIR)
        assert payload is not None
        assert "ticker" not in payload

    def test_no_none_values(self):
        payload = parse_company_frontmatter(SBER_DIR)
        assert payload is not None
        for k, v in payload.items():
            assert v is not None, f"Field {k} should not be None"

    def test_template_skipped(self):
        template_dir = PROJECT_ROOT / "companies" / "_TEMPLATE"
        assert parse_company_frontmatter(template_dir) is None

    def test_nonexistent_dir(self):
        assert parse_company_frontmatter(Path("/nonexistent")) is None


# ---------------------------------------------------------------------------
# Catalysts from frontmatter
# ---------------------------------------------------------------------------


class TestExtractCatalysts:
    def test_sber_catalysts(self):
        catalysts = extract_catalysts_from_frontmatter(SBER_DIR)
        assert len(catalysts) > 0

        opportunities = [c for c in catalysts if c["type"] == "opportunity"]
        risks = [c for c in catalysts if c["type"] == "risk"]
        assert len(opportunities) > 0
        assert len(risks) > 0

    def test_catalyst_structure(self):
        catalysts = extract_catalysts_from_frontmatter(SBER_DIR)
        for c in catalysts:
            assert c["type"] in ("opportunity", "risk")
            assert c["impact"] in ("positive", "negative")
            assert c["magnitude"] == "medium"
            assert c["source"] == "index"
            assert c["is_active"] is True
            assert isinstance(c["description"], str)
            assert len(c["description"]) > 0

    def test_nonexistent_returns_empty(self):
        assert extract_catalysts_from_frontmatter(Path("/nonexistent")) == []


# ---------------------------------------------------------------------------
# News parsing
# ---------------------------------------------------------------------------


class TestParseNews:
    def test_sber_news(self):
        news = parse_news(SBER_DIR)
        assert len(news) > 0
        first = news[0]
        assert "date" in first
        assert "title" in first

    def test_valid_enum_values(self):
        news = parse_news(SBER_DIR)
        for item in news:
            if "impact" in item:
                assert item["impact"] in ("positive", "negative", "mixed", "neutral")
            if "strength" in item:
                assert item["strength"] in ("high", "medium", "low")
            if "action" in item:
                assert item["action"] in ("buy", "hold", "sell")

    def test_nonexistent_returns_empty(self):
        assert parse_news(Path("/nonexistent")) == []


# ---------------------------------------------------------------------------
# Trade signals parsing
# ---------------------------------------------------------------------------


class TestParseTradeSignals:
    def test_sber_signals(self):
        signals = parse_trade_signals(SBER_DIR)
        assert len(signals) > 0
        first = signals[0]
        assert first["signal"] in ("buy", "skip")
        assert first["direction"] in ("long_positive", "long_oversold", "skip")
        assert 0 <= first["confidence"] <= 100

    def test_confidence_is_numeric(self):
        signals = parse_trade_signals(SBER_DIR)
        for s in signals:
            assert isinstance(s["confidence"], (int, float))

    def test_nonexistent_returns_empty(self):
        assert parse_trade_signals(Path("/nonexistent")) == []


# ---------------------------------------------------------------------------
# to_decimal helper
# ---------------------------------------------------------------------------


class TestToDecimal:
    def test_integer(self):
        assert to_decimal(42) == 42

    def test_float(self):
        assert to_decimal(3.14) == 3.14

    def test_string_number(self):
        assert to_decimal("123.45") == 123.45

    def test_percentage(self):
        assert to_decimal("25%") == 25.0

    def test_none(self):
        assert to_decimal(None) is None

    def test_non_numeric(self):
        assert to_decimal("not a number") is None

    def test_comma_decimal(self):
        assert to_decimal("3,14") == 3.14


# ---------------------------------------------------------------------------
# discover_companies
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
# SyncClient methods (unit tests with mocked HTTP)
# ---------------------------------------------------------------------------


class TestSyncClientUpdateCompany:
    def test_update_success(self):
        client = SyncClient("http://test", "key")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        client._put = MagicMock(return_value=mock_resp)
        client._get = MagicMock(return_value=None)

        result = client.update_company("SBER", {"name": "Sberbank"})
        assert result is True
        assert client.stats["companies"]["ok"] == 1

    def test_update_creates_on_404(self):
        client = SyncClient("http://test", "key")

        put_resp = MagicMock()
        put_resp.status_code = 404
        put_resp.text = "Not found"

        post_resp = MagicMock()
        post_resp.status_code = 201
        post_resp.json.return_value = {"id": 1}

        client._put = MagicMock(return_value=put_resp)
        client._post = MagicMock(return_value=post_resp)
        client._get = MagicMock(return_value=None)

        result = client.update_company("SBER", {"name": "Sberbank"})
        assert result is True
        assert client.stats["companies"]["ok"] == 1
        # Should have added ticker to the POST payload
        post_call_payload = client._post.call_args[0][1]
        assert post_call_payload["ticker"] == "SBER"


class TestSyncClientSyncCatalysts:
    def test_deactivates_old_and_creates_new(self):
        client = SyncClient("http://test", "key")

        # Mock GET existing catalysts
        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.json.return_value = [
            {"id": 1, "source": "index", "is_active": True},
            {"id": 2, "source": "macro", "is_active": True},
        ]

        put_resp = MagicMock()
        put_resp.status_code = 200

        post_resp = MagicMock()
        post_resp.status_code = 201

        client._get = MagicMock(return_value=get_resp)
        client._put = MagicMock(return_value=put_resp)
        client._post = MagicMock(return_value=post_resp)

        new_catalysts = [
            {"type": "opportunity", "impact": "positive", "magnitude": "medium",
             "description": "New opp", "source": "index", "is_active": True},
        ]
        client.sync_catalysts("SBER", new_catalysts)

        # Should deactivate only the index-sourced catalyst (id=1), not macro (id=2)
        assert client.stats["catalysts_deactivated"]["ok"] == 1
        assert client.stats["catalysts_created"]["ok"] == 1


class TestSyncClientSyncNews:
    def test_skips_duplicates(self):
        client = SyncClient("http://test", "key")

        # Mock get company id
        get_company_resp = MagicMock()
        get_company_resp.status_code = 200
        get_company_resp.json.return_value = {"id": 1}

        # Mock existing news
        get_news_resp = MagicMock()
        get_news_resp.status_code = 200
        get_news_resp.json.return_value = [
            {"date": "2026-01-01", "title": "Existing news"},
        ]

        post_resp = MagicMock()
        post_resp.status_code = 201

        def mock_get(path, params=None):
            if "/companies/" in path and "/news" in path:
                return get_news_resp
            return get_company_resp

        client._get = MagicMock(side_effect=mock_get)
        client._post = MagicMock(return_value=post_resp)

        news_payloads = [
            {"date": "2026-01-01", "title": "Existing news"},  # duplicate
            {"date": "2026-01-02", "title": "New news"},  # new
        ]
        client.sync_news("SBER", news_payloads)

        # Only the new one should be created
        assert client.stats["news"]["ok"] == 1
        assert client._post.call_count == 1


class TestSyncClientSyncSignals:
    def test_skips_duplicates_by_composite_key(self):
        client = SyncClient("http://test", "key")

        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.json.return_value = [
            {"date": "2026-01-01", "signal": "buy", "direction": "long_positive"},
        ]

        post_resp = MagicMock()
        post_resp.status_code = 201

        client._get = MagicMock(return_value=get_resp)
        client._post = MagicMock(return_value=post_resp)

        signal_payloads = [
            {"date": "2026-01-01", "signal": "buy", "direction": "long_positive", "confidence": 75},
            {"date": "2026-01-02", "signal": "skip", "direction": "skip", "confidence": 50},
        ]
        client.sync_signals("SBER", signal_payloads)

        assert client.stats["signals"]["ok"] == 1
        assert client._post.call_count == 1


# ---------------------------------------------------------------------------
# Integration: full sync flow
# ---------------------------------------------------------------------------


class TestSyncTickerIntegration:
    def test_sync_calls_all_methods(self):
        """Verify sync_ticker calls update_company, sync_catalysts, sync_news, sync_signals."""
        client = SyncClient("http://test", "key")

        client.update_company = MagicMock(return_value=True)
        client.sync_catalysts = MagicMock()
        client.sync_news = MagicMock()
        client.sync_signals = MagicMock()

        sync_ticker(client, "SBER")

        client.update_company.assert_called_once()
        client.sync_catalysts.assert_called_once()
        client.sync_news.assert_called_once()
        client.sync_signals.assert_called_once()

    def test_sync_skips_invalid_ticker(self):
        client = SyncClient("http://test", "key")
        client.update_company = MagicMock()

        sync_ticker(client, "NONEXISTENT_TICKER_XYZ")

        client.update_company.assert_not_called()
