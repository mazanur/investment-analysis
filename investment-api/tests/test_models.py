from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    Catalyst,
    Company,
    Dividend,
    FinancialReport,
    News,
    Price,
    Sector,
    TradeSignal,
)
from app.models.enums import (
    ActionEnum,
    CatalystTypeEnum,
    DirectionEnum,
    DividendStatusEnum,
    ImpactEnum,
    MagnitudeEnum,
    PeriodTypeEnum,
    PositionEnum,
    PositionSizeEnum,
    SentimentEnum,
    SignalEnum,
    SignalStatusEnum,
    StrengthEnum,
)


# --- Sector ---


@pytest.mark.asyncio
async def test_create_sector(db_session):
    sector = Sector(slug="finance", name="Финансы", description="Банки и страховые")
    db_session.add(sector)
    await db_session.commit()

    result = await db_session.execute(select(Sector).where(Sector.slug == "finance"))
    s = result.scalar_one()
    assert s.name == "Финансы"
    assert s.description == "Банки и страховые"
    assert s.id is not None


@pytest.mark.asyncio
async def test_sector_slug_unique(db_session):
    db_session.add(Sector(slug="finance", name="Финансы"))
    await db_session.commit()

    db_session.add(Sector(slug="finance", name="Другое"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


# --- Company ---


@pytest.mark.asyncio
async def test_create_company(db_session):
    sector = Sector(slug="finance", name="Финансы")
    db_session.add(sector)
    await db_session.flush()

    company = Company(
        ticker="SBER",
        sector_id=sector.id,
        name="Сбербанк",
        subsector="Банки",
        sentiment=SentimentEnum.bullish,
        position=PositionEnum.buy,
        my_fair_value=Decimal("400.00"),
        current_price=Decimal("300.00"),
        upside=Decimal("0.3333"),
        p_e=Decimal("4.50"),
        dividend_yield=Decimal("12.00"),
        roe=Decimal("25.00"),
    )
    db_session.add(company)
    await db_session.commit()

    result = await db_session.execute(select(Company).where(Company.ticker == "SBER"))
    c = result.scalar_one()
    assert c.name == "Сбербанк"
    assert c.sentiment == SentimentEnum.bullish
    assert c.position == PositionEnum.buy
    assert c.sector_id == sector.id


@pytest.mark.asyncio
async def test_company_ticker_unique(db_session):
    db_session.add(Company(ticker="SBER", name="Сбербанк"))
    await db_session.commit()

    db_session.add(Company(ticker="SBER", name="Другой"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_company_without_sector(db_session):
    company = Company(ticker="SBER", name="Сбербанк", sector_id=None)
    db_session.add(company)
    await db_session.commit()

    result = await db_session.execute(select(Company).where(Company.ticker == "SBER"))
    c = result.scalar_one()
    assert c.sector_id is None


# --- FinancialReport ---


@pytest.mark.asyncio
async def test_create_financial_report(db_session):
    company = Company(ticker="SBER", name="Сбербанк")
    db_session.add(company)
    await db_session.flush()

    report = FinancialReport(
        company_id=company.id,
        period="2024Q3",
        period_type=PeriodTypeEnum.quarterly,
        report_date=date(2024, 11, 15),
        net_income=Decimal("500000.00"),
        revenue=Decimal("1200000.00"),
        roe=Decimal("25.50"),
        extra_metrics={"nim": 6.2, "npl_ratio": 2.1},
    )
    db_session.add(report)
    await db_session.commit()

    result = await db_session.execute(select(FinancialReport).where(FinancialReport.company_id == company.id))
    r = result.scalar_one()
    assert r.period == "2024Q3"
    assert r.period_type == PeriodTypeEnum.quarterly
    assert r.extra_metrics == {"nim": 6.2, "npl_ratio": 2.1}


@pytest.mark.asyncio
async def test_financial_report_unique_company_period(db_session):
    company = Company(ticker="SBER", name="Сбербанк")
    db_session.add(company)
    await db_session.flush()

    db_session.add(FinancialReport(company_id=company.id, period="2024Q3", period_type=PeriodTypeEnum.quarterly))
    await db_session.commit()

    db_session.add(FinancialReport(company_id=company.id, period="2024Q3", period_type=PeriodTypeEnum.quarterly))
    with pytest.raises(IntegrityError):
        await db_session.commit()


# --- Dividend ---


@pytest.mark.asyncio
async def test_create_dividend(db_session):
    company = Company(ticker="SBER", name="Сбербанк")
    db_session.add(company)
    await db_session.flush()

    div = Dividend(
        company_id=company.id,
        record_date=date(2024, 7, 15),
        amount=Decimal("33.30"),
        currency="RUB",
        yield_pct=Decimal("12.50"),
        period_label="2023",
        status=DividendStatusEnum.confirmed,
    )
    db_session.add(div)
    await db_session.commit()

    result = await db_session.execute(select(Dividend).where(Dividend.company_id == company.id))
    d = result.scalar_one()
    assert d.amount == Decimal("33.30")
    assert d.status == DividendStatusEnum.confirmed


@pytest.mark.asyncio
async def test_dividend_unique_company_date(db_session):
    company = Company(ticker="SBER", name="Сбербанк")
    db_session.add(company)
    await db_session.flush()

    db_session.add(Dividend(company_id=company.id, record_date=date(2024, 7, 15), amount=Decimal("33.30")))
    await db_session.commit()

    db_session.add(Dividend(company_id=company.id, record_date=date(2024, 7, 15), amount=Decimal("10.00")))
    with pytest.raises(IntegrityError):
        await db_session.commit()


# --- Catalyst ---


@pytest.mark.asyncio
async def test_create_catalyst_with_company(db_session):
    company = Company(ticker="SBER", name="Сбербанк")
    db_session.add(company)
    await db_session.flush()

    cat = Catalyst(
        company_id=company.id,
        type=CatalystTypeEnum.opportunity,
        impact=ImpactEnum.positive,
        magnitude=MagnitudeEnum.high,
        description="Высокие дивиденды",
        is_active=True,
    )
    db_session.add(cat)
    await db_session.commit()

    result = await db_session.execute(select(Catalyst).where(Catalyst.company_id == company.id))
    c = result.scalar_one()
    assert c.type == CatalystTypeEnum.opportunity
    assert c.magnitude == MagnitudeEnum.high


@pytest.mark.asyncio
async def test_create_macro_catalyst_without_company(db_session):
    cat = Catalyst(
        company_id=None,
        type=CatalystTypeEnum.cb_meeting,
        impact=ImpactEnum.mixed,
        magnitude=MagnitudeEnum.high,
        date=date(2024, 12, 20),
        description="Заседание ЦБ — ожидается повышение ставки",
    )
    db_session.add(cat)
    await db_session.commit()

    result = await db_session.execute(select(Catalyst).where(Catalyst.type == CatalystTypeEnum.cb_meeting))
    c = result.scalar_one()
    assert c.company_id is None
    assert c.date == date(2024, 12, 20)


# --- Price ---


@pytest.mark.asyncio
async def test_create_price(db_session):
    company = Company(ticker="SBER", name="Сбербанк")
    db_session.add(company)
    await db_session.flush()

    price = Price(
        company_id=company.id,
        date=date(2024, 12, 1),
        open=Decimal("290.00"),
        high=Decimal("305.00"),
        low=Decimal("288.00"),
        close=Decimal("300.00"),
        volume_rub=Decimal("15000000000.00"),
    )
    db_session.add(price)
    await db_session.commit()

    result = await db_session.execute(select(Price).where(Price.company_id == company.id))
    p = result.scalar_one()
    assert p.close == Decimal("300.00")
    assert p.volume_rub == Decimal("15000000000.00")


@pytest.mark.asyncio
async def test_price_unique_company_date(db_session):
    company = Company(ticker="SBER", name="Сбербанк")
    db_session.add(company)
    await db_session.flush()

    db_session.add(Price(company_id=company.id, date=date(2024, 12, 1), close=Decimal("300.00")))
    await db_session.commit()

    db_session.add(Price(company_id=company.id, date=date(2024, 12, 1), close=Decimal("310.00")))
    with pytest.raises(IntegrityError):
        await db_session.commit()


# --- News ---


@pytest.mark.asyncio
async def test_create_news_for_company(db_session):
    company = Company(ticker="SBER", name="Сбербанк")
    db_session.add(company)
    await db_session.flush()

    n = News(
        company_id=company.id,
        date=date(2024, 12, 1),
        title="Сбербанк объявил дивиденды",
        source="moex.com",
        impact=ImpactEnum.positive,
        strength=StrengthEnum.high,
        action=ActionEnum.buy,
    )
    db_session.add(n)
    await db_session.commit()

    result = await db_session.execute(select(News).where(News.company_id == company.id))
    news = result.scalar_one()
    assert news.title == "Сбербанк объявил дивиденды"
    assert news.impact == ImpactEnum.positive
    assert news.strength == StrengthEnum.high


@pytest.mark.asyncio
async def test_create_news_for_sector(db_session):
    sector = Sector(slug="finance", name="Финансы")
    db_session.add(sector)
    await db_session.flush()

    n = News(
        sector_id=sector.id,
        company_id=None,
        date=date(2024, 12, 1),
        title="Банковский сектор под давлением",
        impact=ImpactEnum.negative,
    )
    db_session.add(n)
    await db_session.commit()

    result = await db_session.execute(select(News).where(News.sector_id == sector.id))
    news = result.scalar_one()
    assert news.company_id is None
    assert news.sector_id == sector.id


@pytest.mark.asyncio
async def test_create_macro_news(db_session):
    n = News(
        company_id=None,
        sector_id=None,
        date=date(2024, 12, 1),
        title="ЦБ повысил ставку до 23%",
        impact=ImpactEnum.negative,
        strength=StrengthEnum.high,
    )
    db_session.add(n)
    await db_session.commit()

    result = await db_session.execute(select(News))
    news = result.scalar_one()
    assert news.company_id is None
    assert news.sector_id is None


# --- TradeSignal ---


@pytest.mark.asyncio
async def test_create_trade_signal(db_session):
    company = Company(ticker="SBER", name="Сбербанк")
    db_session.add(company)
    await db_session.flush()

    signal = TradeSignal(
        company_id=company.id,
        date=date(2024, 12, 1),
        signal=SignalEnum.buy,
        direction=DirectionEnum.long_positive,
        confidence=Decimal("75.00"),
        entry_price=Decimal("300.00"),
        take_profit=Decimal("350.00"),
        stop_loss=Decimal("280.00"),
        time_limit_days=30,
        expected_return_pct=Decimal("16.67"),
        risk_reward=Decimal("2.50"),
        position_size=PositionSizeEnum.full,
        reasoning="Дивиденды + рост прибыли",
        status=SignalStatusEnum.active,
    )
    db_session.add(signal)
    await db_session.commit()

    result = await db_session.execute(select(TradeSignal).where(TradeSignal.company_id == company.id))
    s = result.scalar_one()
    assert s.signal == SignalEnum.buy
    assert s.direction == DirectionEnum.long_positive
    assert s.confidence == Decimal("75.00")
    assert s.status == SignalStatusEnum.active


@pytest.mark.asyncio
async def test_trade_signal_with_news_fk(db_session):
    company = Company(ticker="SBER", name="Сбербанк")
    db_session.add(company)
    await db_session.flush()

    news = News(company_id=company.id, date=date(2024, 12, 1), title="Дивиденды", impact=ImpactEnum.positive)
    db_session.add(news)
    await db_session.flush()

    signal = TradeSignal(
        company_id=company.id,
        news_id=news.id,
        date=date(2024, 12, 1),
        signal=SignalEnum.buy,
        direction=DirectionEnum.long_positive,
        confidence=Decimal("80.00"),
        status=SignalStatusEnum.active,
    )
    db_session.add(signal)
    await db_session.commit()

    result = await db_session.execute(select(TradeSignal).where(TradeSignal.news_id == news.id))
    s = result.scalar_one()
    assert s.news_id == news.id


@pytest.mark.asyncio
async def test_trade_signal_without_news(db_session):
    company = Company(ticker="SBER", name="Сбербанк")
    db_session.add(company)
    await db_session.flush()

    signal = TradeSignal(
        company_id=company.id,
        news_id=None,
        date=date(2024, 12, 1),
        signal=SignalEnum.skip,
        direction=DirectionEnum.skip,
        confidence=Decimal("30.00"),
        status=SignalStatusEnum.active,
    )
    db_session.add(signal)
    await db_session.commit()

    result = await db_session.execute(select(TradeSignal).where(TradeSignal.company_id == company.id))
    s = result.scalar_one()
    assert s.news_id is None


# --- Enum values ---


@pytest.mark.asyncio
async def test_all_sentiment_values(db_session):
    for i, s in enumerate(SentimentEnum):
        db_session.add(Company(ticker=f"T{i}", name=f"Company {i}", sentiment=s))
    await db_session.commit()
    result = await db_session.execute(select(Company))
    companies = result.scalars().all()
    assert len(companies) == 3


@pytest.mark.asyncio
async def test_all_position_values(db_session):
    for i, p in enumerate(PositionEnum):
        db_session.add(Company(ticker=f"P{i}", name=f"Company {i}", position=p))
    await db_session.commit()
    result = await db_session.execute(select(Company))
    companies = result.scalars().all()
    assert len(companies) == 5
