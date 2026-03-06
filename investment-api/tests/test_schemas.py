from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas import (
    CatalystCreate,
    CatalystResponse,
    CompanyCreate,
    CompanyFilter,
    CompanyListResponse,
    CompanyResponse,
    DividendCreate,
    FinancialReportCreate,
    NewsCreate,
    PriceBulkCreate,
    PriceCreate,
    SectorCreate,
    SectorResponse,
    SectorUpdate,
    TradeSignalCreate,
    TradeSignalUpdate,
)


class TestSectorSchemas:
    def test_sector_create(self):
        s = SectorCreate(slug="finance", name="Finance")
        assert s.slug == "finance"
        assert s.description is None

    def test_sector_create_with_description(self):
        s = SectorCreate(slug="it", name="IT & Telecom", description="Tech sector")
        assert s.description == "Tech sector"

    def test_sector_update_partial(self):
        s = SectorUpdate(name="Updated Name")
        assert s.name == "Updated Name"
        assert s.description is None

    def test_sector_response_from_attributes(self):
        data = {
            "id": 1,
            "slug": "finance",
            "name": "Finance",
            "description": None,
            "updated_at": datetime(2026, 1, 1),
        }
        s = SectorResponse.model_validate(data)
        assert s.id == 1
        assert s.slug == "finance"


class TestCompanySchemas:
    def test_company_create_minimal(self):
        c = CompanyCreate(ticker="SBER", name="Sberbank")
        assert c.ticker == "SBER"
        assert c.sentiment is None
        assert c.position is None

    def test_company_create_full(self):
        c = CompanyCreate(
            ticker="SBER",
            name="Sberbank",
            sector_id=1,
            sentiment="bullish",
            position="buy",
            my_fair_value=Decimal("400.00"),
            current_price=Decimal("300.00"),
            upside=Decimal("0.3333"),
            p_e=Decimal("4.50"),
            dividend_yield=Decimal("12.00"),
        )
        assert c.sentiment == "bullish"
        assert c.position == "buy"
        assert c.my_fair_value == Decimal("400.00")

    def test_company_create_invalid_sentiment(self):
        with pytest.raises(ValidationError, match="sentiment"):
            CompanyCreate(ticker="SBER", name="Sberbank", sentiment="very_bullish")

    def test_company_create_invalid_position(self):
        with pytest.raises(ValidationError, match="position"):
            CompanyCreate(ticker="SBER", name="Sberbank", position="strong_buy")

    def test_company_list_response(self):
        data = {
            "id": 1,
            "ticker": "SBER",
            "name": "Sberbank",
            "updated_at": datetime(2026, 1, 1),
        }
        c = CompanyListResponse.model_validate(data)
        assert c.ticker == "SBER"
        assert c.subsector is None

    def test_company_response_with_nested(self):
        data = {
            "id": 1,
            "ticker": "SBER",
            "name": "Sberbank",
            "updated_at": datetime(2026, 1, 1),
            "latest_price": {
                "id": 1,
                "company_id": 1,
                "date": date(2026, 3, 5),
                "close": Decimal("300.00"),
                "created_at": datetime(2026, 3, 5),
            },
            "active_catalysts": [
                {
                    "id": 1,
                    "type": "opportunity",
                    "impact": "positive",
                    "magnitude": "high",
                    "description": "Strong earnings",
                    "is_active": True,
                    "created_at": datetime(2026, 1, 1),
                }
            ],
            "last_dividend": {
                "id": 1,
                "company_id": 1,
                "record_date": date(2026, 6, 15),
                "amount": Decimal("33.30"),
                "currency": "RUB",
                "status": "announced",
                "created_at": datetime(2026, 1, 1),
            },
        }
        c = CompanyResponse.model_validate(data)
        assert c.latest_price is not None
        assert c.latest_price.close == Decimal("300.00")
        assert len(c.active_catalysts) == 1
        assert c.last_dividend is not None
        assert c.last_dividend.amount == Decimal("33.30")

    def test_company_response_without_nested(self):
        data = {
            "id": 1,
            "ticker": "SBER",
            "name": "Sberbank",
            "updated_at": datetime(2026, 1, 1),
        }
        c = CompanyResponse.model_validate(data)
        assert c.latest_price is None
        assert c.active_catalysts == []
        assert c.last_dividend is None

    def test_company_filter(self):
        f = CompanyFilter(
            sector="finance",
            sentiment="bullish",
            min_upside=Decimal("0.20"),
            max_p_e=Decimal("10.00"),
        )
        assert f.sector == "finance"
        assert f.sentiment == "bullish"

    def test_company_filter_empty(self):
        f = CompanyFilter()
        assert f.sector is None
        assert f.sentiment is None


class TestFinancialReportSchemas:
    def test_create_valid(self):
        r = FinancialReportCreate(
            period="2025Q3",
            period_type="quarterly",
            revenue=Decimal("1500000"),
            net_income=Decimal("300000"),
        )
        assert r.period == "2025Q3"
        assert r.extra_metrics is None

    def test_create_with_extra_metrics(self):
        r = FinancialReportCreate(
            period="2025",
            period_type="yearly",
            extra_metrics={"nim": 6.2, "npl_ratio": 2.1, "cost_income": 28.5},
        )
        assert r.extra_metrics["nim"] == 6.2

    def test_extra_metrics_invalid_value_type(self):
        with pytest.raises(ValidationError, match="extra_metrics"):
            FinancialReportCreate(
                period="2025",
                period_type="yearly",
                extra_metrics={"nim": "not a number"},
            )

    def test_invalid_period_type(self):
        with pytest.raises(ValidationError, match="period_type"):
            FinancialReportCreate(period="2025", period_type="monthly")


class TestDividendSchemas:
    def test_create_minimal(self):
        d = DividendCreate(record_date=date(2026, 6, 15), amount=Decimal("33.30"))
        assert d.currency == "RUB"
        assert d.status == "announced"

    def test_create_full(self):
        d = DividendCreate(
            record_date=date(2026, 6, 15),
            amount=Decimal("33.30"),
            currency="RUB",
            yield_pct=Decimal("11.00"),
            period_label="2025H2",
            status="confirmed",
        )
        assert d.status == "confirmed"
        assert d.yield_pct == Decimal("11.00")

    def test_invalid_status(self):
        with pytest.raises(ValidationError, match="status"):
            DividendCreate(
                record_date=date(2026, 6, 15),
                amount=Decimal("33.30"),
                status="pending",
            )


class TestCatalystSchemas:
    def test_create_company_catalyst(self):
        c = CatalystCreate(
            company_id=1,
            type="opportunity",
            impact="positive",
            description="Strong Q3 earnings expected",
        )
        assert c.magnitude == "medium"
        assert c.is_active is True

    def test_create_macro_catalyst(self):
        c = CatalystCreate(
            type="cb_meeting",
            impact="mixed",
            magnitude="high",
            date=date(2026, 3, 21),
            description="CB rate decision",
        )
        assert c.company_id is None

    def test_response(self):
        data = {
            "id": 1,
            "company_id": None,
            "type": "cb_meeting",
            "impact": "mixed",
            "magnitude": "high",
            "description": "CB rate decision",
            "is_active": True,
            "created_at": datetime(2026, 1, 1),
        }
        c = CatalystResponse.model_validate(data)
        assert c.company_id is None
        assert c.type == "cb_meeting"


class TestPriceSchemas:
    def test_create_minimal(self):
        p = PriceCreate(date=date(2026, 3, 5), close=Decimal("300.00"))
        assert p.open is None
        assert p.volume_rub is None

    def test_create_full(self):
        p = PriceCreate(
            date=date(2026, 3, 5),
            open=Decimal("298.00"),
            high=Decimal("305.00"),
            low=Decimal("297.00"),
            close=Decimal("300.00"),
            volume_rub=Decimal("1500000000"),
        )
        assert p.high == Decimal("305.00")

    def test_bulk_create(self):
        bulk = PriceBulkCreate(
            prices=[
                PriceCreate(date=date(2026, 3, 4), close=Decimal("299.00")),
                PriceCreate(date=date(2026, 3, 5), close=Decimal("300.00")),
            ]
        )
        assert len(bulk.prices) == 2

    def test_bulk_create_empty(self):
        bulk = PriceBulkCreate(prices=[])
        assert len(bulk.prices) == 0

    def test_create_missing_close(self):
        with pytest.raises(ValidationError, match="close"):
            PriceCreate(date=date(2026, 3, 5))


class TestNewsSchemas:
    def test_create_company_news(self):
        n = NewsCreate(
            company_id=1,
            date=date(2026, 3, 5),
            title="SBER Q4 results above expectations",
            impact="positive",
            strength="high",
        )
        assert n.sector_id is None

    def test_create_macro_news(self):
        n = NewsCreate(
            date=date(2026, 3, 5),
            title="CB holds rate at 21%",
            source="cbr.ru",
        )
        assert n.company_id is None
        assert n.sector_id is None

    def test_create_sector_news(self):
        n = NewsCreate(
            sector_id=1,
            date=date(2026, 3, 5),
            title="Oil prices surge",
        )
        assert n.company_id is None
        assert n.sector_id == 1


class TestTradeSignalSchemas:
    def test_create_valid(self):
        ts = TradeSignalCreate(
            date=date(2026, 3, 5),
            signal="buy",
            direction="long-positive",
            confidence=Decimal("75.00"),
            entry_price=Decimal("300.00"),
            take_profit=Decimal("350.00"),
            stop_loss=Decimal("280.00"),
            risk_reward=Decimal("2.50"),
            position_size="full",
        )
        assert ts.status == "active"
        assert ts.confidence == Decimal("75.00")

    def test_confidence_below_zero(self):
        with pytest.raises(ValidationError, match="confidence"):
            TradeSignalCreate(
                date=date(2026, 3, 5),
                signal="buy",
                direction="long-positive",
                confidence=Decimal("-1"),
            )

    def test_confidence_above_100(self):
        with pytest.raises(ValidationError, match="confidence"):
            TradeSignalCreate(
                date=date(2026, 3, 5),
                signal="buy",
                direction="long-positive",
                confidence=Decimal("101"),
            )

    def test_confidence_boundary_values(self):
        ts0 = TradeSignalCreate(
            date=date(2026, 3, 5),
            signal="buy",
            direction="long-positive",
            confidence=Decimal("0"),
        )
        assert ts0.confidence == Decimal("0")

        ts100 = TradeSignalCreate(
            date=date(2026, 3, 5),
            signal="buy",
            direction="long-positive",
            confidence=Decimal("100"),
        )
        assert ts100.confidence == Decimal("100")

    def test_negative_risk_reward(self):
        with pytest.raises(ValidationError, match="risk_reward"):
            TradeSignalCreate(
                date=date(2026, 3, 5),
                signal="buy",
                direction="long-positive",
                confidence=Decimal("50"),
                risk_reward=Decimal("-1"),
            )

    def test_risk_reward_zero(self):
        ts = TradeSignalCreate(
            date=date(2026, 3, 5),
            signal="buy",
            direction="long-positive",
            confidence=Decimal("50"),
            risk_reward=Decimal("0"),
        )
        assert ts.risk_reward == Decimal("0")

    def test_update_close_signal(self):
        u = TradeSignalUpdate(
            status="closed",
            result_pct=Decimal("15.50"),
            closed_at=datetime(2026, 3, 10, 18, 0),
        )
        assert u.status == "closed"
        assert u.result_pct == Decimal("15.50")

    def test_invalid_signal_enum(self):
        with pytest.raises(ValidationError, match="signal"):
            TradeSignalCreate(
                date=date(2026, 3, 5),
                signal="sell",
                direction="long-positive",
                confidence=Decimal("50"),
            )

    def test_invalid_direction_enum(self):
        with pytest.raises(ValidationError, match="direction"):
            TradeSignalCreate(
                date=date(2026, 3, 5),
                signal="buy",
                direction="short",
                confidence=Decimal("50"),
            )
