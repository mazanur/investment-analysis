import hmac

from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.config import settings
from app.models.catalyst import Catalyst
from app.models.company import Company
from app.models.dividend import Dividend
from app.models.financial_report import FinancialReport
from app.models.intraday_candle import IntradayCandle
from app.models.order_book_snapshot import OrderBookSnapshot
from app.models.price import Price
from app.models.sector import Sector
from app.models.job_run import JobRun
from app.models.price_snapshot import PriceSnapshot


class ApiKeyAuth(AuthenticationBackend):
    """Simple API key authentication for admin panel."""

    async def login(self, request: Request) -> bool:
        form = await request.form()
        api_key = form.get("username", "")
        if hmac.compare_digest(str(api_key), settings.api_key):
            request.session.update({"authenticated": True})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return request.session.get("authenticated", False)


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
        Company.figi,
        Company.lot_size,
        Company.updated_at,
    ]
    column_select_related_list = ["sector"]
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
    column_select_related_list = ["company"]
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
    column_select_related_list = ["company"]
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
    column_select_related_list = ["company"]
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
    column_select_related_list = ["company"]
    column_sortable_list = [Price.id, Price.date, Price.close, Price.volume_rub]
    column_default_sort = ("date", True)
    page_size = 50
    icon = "fa-solid fa-chart-line"
    name = "Price"
    name_plural = "Prices"


class PriceSnapshotAdmin(ModelView, model=PriceSnapshot):
    column_list = [
        PriceSnapshot.id,
        PriceSnapshot.company,
        PriceSnapshot.timestamp,
        PriceSnapshot.price,
        PriceSnapshot.volume_rub,
    ]
    column_select_related_list = ["company"]
    column_sortable_list = [PriceSnapshot.id, PriceSnapshot.timestamp, PriceSnapshot.price]
    column_default_sort = ("timestamp", True)
    page_size = 50
    can_create = False
    can_edit = False
    can_delete = False
    icon = "fa-solid fa-clock"
    name = "Price Snapshot"
    name_plural = "Price Snapshots"


class OrderBookSnapshotAdmin(ModelView, model=OrderBookSnapshot):
    column_list = [
        OrderBookSnapshot.id,
        OrderBookSnapshot.company,
        OrderBookSnapshot.timestamp,
        OrderBookSnapshot.best_bid,
        OrderBookSnapshot.best_ask,
        OrderBookSnapshot.spread_pct,
    ]
    column_select_related_list = ["company"]
    column_sortable_list = [OrderBookSnapshot.id, OrderBookSnapshot.timestamp, OrderBookSnapshot.spread_pct]
    column_default_sort = ("timestamp", True)
    page_size = 50
    can_create = False
    can_edit = False
    can_delete = False
    icon = "fa-solid fa-book-open"
    name = "Order Book"
    name_plural = "Order Books"


class IntradayCandleAdmin(ModelView, model=IntradayCandle):
    column_list = [
        IntradayCandle.id,
        IntradayCandle.company,
        IntradayCandle.timestamp,
        IntradayCandle.interval,
        IntradayCandle.open,
        IntradayCandle.high,
        IntradayCandle.low,
        IntradayCandle.close,
        IntradayCandle.volume,
    ]
    column_select_related_list = ["company"]
    column_sortable_list = [IntradayCandle.id, IntradayCandle.timestamp, IntradayCandle.interval]
    column_default_sort = ("timestamp", True)
    page_size = 50
    can_create = False
    can_edit = False
    can_delete = False
    icon = "fa-solid fa-chart-bar"
    name = "Intraday Candle"
    name_plural = "Intraday Candles"


class JobRunAdmin(ModelView, model=JobRun):
    column_list = [
        JobRun.id,
        JobRun.job_name,
        JobRun.status,
        JobRun.started_at,
        JobRun.completed_at,
        JobRun.duration_seconds,
        JobRun.result,
        JobRun.error,
    ]
    column_searchable_list = [JobRun.job_name]
    column_sortable_list = [JobRun.id, JobRun.job_name, JobRun.status, JobRun.started_at, JobRun.duration_seconds]
    column_default_sort = ("started_at", True)
    page_size = 50
    can_create = False
    can_edit = False
    can_delete = False
    icon = "fa-solid fa-clock-rotate-left"
    name = "Job Run"
    name_plural = "Job Runs"


def setup_admin(app, engine):
    auth_backend = ApiKeyAuth(secret_key=settings.secret_key)
    admin = Admin(app, engine, title="Investment Admin", authentication_backend=auth_backend)
    admin.add_view(SectorAdmin)
    admin.add_view(CompanyAdmin)
    admin.add_view(FinancialReportAdmin)
    admin.add_view(DividendAdmin)
    admin.add_view(CatalystAdmin)
    admin.add_view(PriceAdmin)
    admin.add_view(PriceSnapshotAdmin)
    admin.add_view(OrderBookSnapshotAdmin)
    admin.add_view(IntradayCandleAdmin)
    admin.add_view(JobRunAdmin)
    return admin
