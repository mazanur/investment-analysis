from sqladmin import Admin, ModelView

from app.models.catalyst import Catalyst
from app.models.company import Company
from app.models.dividend import Dividend
from app.models.financial_report import FinancialReport
from app.models.news import News
from app.models.price import Price
from app.models.sector import Sector
from app.models.trade_signal import TradeSignal


class SectorAdmin(ModelView, model=Sector):
    column_list = [Sector.id, Sector.slug, Sector.name, Sector.updated_at]
    column_searchable_list = [Sector.slug, Sector.name]
    column_sortable_list = [Sector.id, Sector.slug, Sector.name, Sector.updated_at]
    column_default_sort = "slug"
    icon = "fa-solid fa-layer-group"
    name = "Sector"
    name_plural = "Sectors"


class CompanyAdmin(ModelView, model=Company):
    column_list = [
        Company.id,
        Company.ticker,
        Company.name,
        Company.sector,
        Company.sentiment,
        Company.position,
        Company.current_price,
        Company.my_fair_value,
        Company.upside,
        Company.p_e,
        Company.dividend_yield,
        Company.updated_at,
    ]
    column_searchable_list = [Company.ticker, Company.name]
    column_sortable_list = [
        Company.id, Company.ticker, Company.name, Company.sentiment,
        Company.position, Company.upside, Company.p_e, Company.updated_at,
    ]
    column_default_sort = "ticker"
    icon = "fa-solid fa-building"
    name = "Company"
    name_plural = "Companies"


class FinancialReportAdmin(ModelView, model=FinancialReport):
    column_list = [
        FinancialReport.id,
        FinancialReport.company,
        FinancialReport.period,
        FinancialReport.period_type,
        FinancialReport.revenue,
        FinancialReport.net_income,
        FinancialReport.roe,
        FinancialReport.p_e,
    ]
    column_searchable_list = [FinancialReport.period]
    column_sortable_list = [FinancialReport.id, FinancialReport.period, FinancialReport.period_type]
    column_default_sort = ("id", True)
    icon = "fa-solid fa-file-invoice-dollar"
    name = "Financial Report"
    name_plural = "Financial Reports"


class DividendAdmin(ModelView, model=Dividend):
    column_list = [
        Dividend.id,
        Dividend.company,
        Dividend.record_date,
        Dividend.amount,
        Dividend.currency,
        Dividend.yield_pct,
        Dividend.status,
        Dividend.period_label,
    ]
    column_sortable_list = [Dividend.id, Dividend.record_date, Dividend.amount, Dividend.status]
    column_default_sort = ("record_date", True)
    icon = "fa-solid fa-money-bill-trend-up"
    name = "Dividend"
    name_plural = "Dividends"


class CatalystAdmin(ModelView, model=Catalyst):
    column_list = [
        Catalyst.id,
        Catalyst.company,
        Catalyst.type,
        Catalyst.impact,
        Catalyst.magnitude,
        Catalyst.date,
        Catalyst.description,
        Catalyst.is_active,
    ]
    column_sortable_list = [Catalyst.id, Catalyst.type, Catalyst.impact, Catalyst.date, Catalyst.is_active]
    column_default_sort = ("date", True)
    icon = "fa-solid fa-bolt"
    name = "Catalyst"
    name_plural = "Catalysts"


class PriceAdmin(ModelView, model=Price):
    column_list = [
        Price.id,
        Price.company,
        Price.date,
        Price.open,
        Price.high,
        Price.low,
        Price.close,
        Price.volume_rub,
    ]
    column_sortable_list = [Price.id, Price.date, Price.close, Price.volume_rub]
    column_default_sort = ("date", True)
    page_size = 50
    icon = "fa-solid fa-chart-line"
    name = "Price"
    name_plural = "Prices"


class NewsAdmin(ModelView, model=News):
    column_list = [
        News.id,
        News.company,
        News.sector,
        News.date,
        News.title,
        News.source,
        News.impact,
        News.strength,
        News.action,
    ]
    column_searchable_list = [News.title, News.source]
    column_sortable_list = [News.id, News.date, News.impact, News.strength]
    column_default_sort = ("date", True)
    icon = "fa-solid fa-newspaper"
    name = "News"
    name_plural = "News"


class TradeSignalAdmin(ModelView, model=TradeSignal):
    column_list = [
        TradeSignal.id,
        TradeSignal.company,
        TradeSignal.date,
        TradeSignal.signal,
        TradeSignal.direction,
        TradeSignal.confidence,
        TradeSignal.entry_price,
        TradeSignal.take_profit,
        TradeSignal.stop_loss,
        TradeSignal.status,
        TradeSignal.result_pct,
    ]
    column_sortable_list = [
        TradeSignal.id, TradeSignal.date, TradeSignal.signal,
        TradeSignal.status, TradeSignal.confidence,
    ]
    column_default_sort = ("date", True)
    icon = "fa-solid fa-signal"
    name = "Trade Signal"
    name_plural = "Trade Signals"


def setup_admin(app, engine):
    admin = Admin(app, engine, title="Investment Admin")
    admin.add_view(SectorAdmin)
    admin.add_view(CompanyAdmin)
    admin.add_view(FinancialReportAdmin)
    admin.add_view(DividendAdmin)
    admin.add_view(CatalystAdmin)
    admin.add_view(PriceAdmin)
    admin.add_view(NewsAdmin)
    admin.add_view(TradeSignalAdmin)
    return admin
