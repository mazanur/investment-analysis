# Investment API — FastAPI + PostgreSQL backend

## Overview

Отдельное Python-приложение (`investment-api`) для хранения структурированных данных инвестиционного анализа. Решает проблему: сейчас данные размазаны по 73 папкам в 7+ форматах (YAML frontmatter, JSON, CSV), и для API приходится парсить файлы или прогонять через LLM.

**Что даёт:**
- Нормализованная PostgreSQL-база с 8 таблицами
- REST API (FastAPI) для чтения/записи данных
- Серверные jobs для автоматического сбора данных (MOEX, SmartLab, RSS)
- SQL-запросы для аналитики: фильтры по сектору, sentiment, upside и т.д.

**Как интегрируется:**
- `investment-analysis` (этот репо) остаётся аналитическим workspace с markdown
- При анализе: `sync_analysis.py` парсит `_index.md` и пушит результаты в API
- Серверные jobs заменяют локальные скрипты (`download_moex.py`, `download_smartlab.py`, `update_prices.py`)
- Внешние потребители (фронтенд, бот, дашборд) читают из API

## Context (from discovery)

**Текущее состояние:**
- 20 Python-скриптов в `scripts/` (все на stdlib, без внешних зависимостей)
- 3 OpenAPI-схемы в `api/` (trend, catalysts, trade-signals)
- Makefile с 30+ targets, включая `make daily` (prices + trends + catalysts + dashboard)
- ~73 компании, 12 секторов
- Скрипты используют `curl` + stdlib для загрузки данных с MOEX ISS API и smart-lab.ru

**Существующие форматы данных (будут нормализованы):**
- YAML frontmatter в `_index.md` → таблица `companies`
- `moex_market.json` → таблицы `companies` (current_price, market_cap) + `prices`
- `price_history.csv` → таблица `prices`
- `smartlab_quarterly.csv` / `smartlab_yearly.csv` → таблица `financial_reports`
- `catalysts.json` → таблица `catalysts`
- `news.json` → таблица `news`
- `trade_signals.json` → таблица `trade_signals`
- `moex_events.json` (dividends) → таблица `dividends`

## Development Approach

- **testing approach**: Regular (code first, then tests)
- Новый репозиторий `investment-api`, не модифицируем текущий (кроме sync-скриптов)
- Каждый task — логически завершённый этап, можно деплоить после каждого
- SQLAlchemy 2.0 async — для совместимости с FastAPI async endpoints
- Alembic для миграций — каждое изменение схемы через миграцию
- Pydantic v2 — валидация на входе/выходе API
- Docker Compose для локальной разработки и деплоя

## Testing Strategy

- **unit tests**: pytest + pytest-asyncio для каждого endpoint и service
- **integration tests**: testcontainers-postgres для тестов с реальной БД
- **API tests**: httpx AsyncClient для тестирования FastAPI endpoints

## Progress Tracking

- mark completed items with `[x]` immediately when done
- add newly discovered tasks with ➕ prefix
- document issues/blockers with ⚠️ prefix

## Database Schema

```
sectors (id, slug, name, description, updated_at)
    │
    ├──< companies (id, ticker UNIQUE, sector_id FK, name, subsector,
    │       sentiment ENUM, position ENUM, my_fair_value, current_price,
    │       upside, market_cap, shares_out, free_float, adv_rub_mln,
    │       p_e, p_bv, dividend_yield, roe, gov_ownership, updated_at)
    │       │
    │       ├──< financial_reports (id, company_id FK, period, period_type ENUM,
    │       │       report_date, net_income, revenue, equity, total_debt,
    │       │       net_debt, roe, eps, p_e, p_bv, dividend_yield,
    │       │       extra_metrics JSONB, created_at)
    │       │       UNIQUE (company_id, period)
    │       │
    │       ├──< dividends (id, company_id FK, record_date, amount,
    │       │       currency, yield_pct, period_label, status ENUM,
    │       │       created_at)
    │       │       UNIQUE (company_id, record_date)
    │       │
    │       ├──< catalysts (id, company_id FK NULL, type ENUM,
    │       │       impact ENUM, magnitude ENUM, date NULL,
    │       │       description, source, is_active, expired_at, created_at)
    │       │
    │       ├──< prices (id, company_id FK, date, open, high, low,
    │       │       close, volume_rub, market_cap, created_at)
    │       │       UNIQUE (company_id, date)
    │       │
    │       ├──< news (id, company_id FK NULL, sector_id FK NULL,
    │       │       date, title, url, source, impact ENUM,
    │       │       strength ENUM, summary, action ENUM, created_at)
    │       │
    │       └──< trade_signals (id, company_id FK, news_id FK NULL,
    │               date, signal ENUM, direction ENUM,
    │               confidence DECIMAL, entry_price, entry_condition,
    │               take_profit, stop_loss, time_limit_days,
    │               expected_return_pct, risk_reward, position_size ENUM,
    │               reasoning, status ENUM, result_pct, closed_at,
    │               created_at)
    │
    └──< news (sector_id FK NULL — новости по сектору)
```

**Ключевые решения:**
- `financial_reports.extra_metrics` — JSONB для секторальных метрик (NIM, NPL для банков; EBITDA, capex для нефтянки)
- `news` — двойной FK: company_id и sector_id (оба nullable, для макро-новостей — оба NULL)
- `trade_signals.confidence` — DECIMAL (0-100) вместо enum
- `catalysts.company_id` — nullable для макро-катализаторов (заседания ЦБ)

## Implementation Steps

### Task 1: Project scaffold — репозиторий и Docker Compose

**Files:**
- Create: `investment-api/pyproject.toml`
- Create: `investment-api/Dockerfile`
- Create: `investment-api/docker-compose.yml`
- Create: `investment-api/app/__init__.py`
- Create: `investment-api/app/main.py`
- Create: `investment-api/app/config.py`
- Create: `investment-api/app/db.py`
- Create: `investment-api/.env.example`
- Create: `investment-api/.gitignore`
- Create: `investment-api/README.md`

- [x] Создать репозиторий `investment-api` с `pyproject.toml` (deps: fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, pydantic, pydantic-settings)
- [x] `app/config.py` — Pydantic Settings (DATABASE_URL, API_KEY, DEBUG)
- [x] `app/db.py` — async engine + sessionmaker (SQLAlchemy 2.0 async)
- [x] `app/main.py` — FastAPI app с lifespan (create_all tables on startup для dev)
- [x] `Dockerfile` (python:3.12-slim, uvicorn)
- [x] `docker-compose.yml` (app + postgres:16)
- [x] `.env.example`, `.gitignore`
- [x] Проверить: `docker compose up` поднимает app + postgres, healthcheck проходит
- [x] Написать тесты: smoke test (GET / → 200), db connection test
- [x] Запустить тесты — должны пройти

### Task 2: SQLAlchemy models — все 8 таблиц

**Files:**
- Create: `investment-api/app/models/__init__.py`
- Create: `investment-api/app/models/sector.py`
- Create: `investment-api/app/models/company.py`
- Create: `investment-api/app/models/financial_report.py`
- Create: `investment-api/app/models/dividend.py`
- Create: `investment-api/app/models/catalyst.py`
- Create: `investment-api/app/models/price.py`
- Create: `investment-api/app/models/news.py`
- Create: `investment-api/app/models/trade_signal.py`

- [x] `models/sector.py` — Sector model (id, slug UNIQUE, name, description, updated_at)
- [x] `models/company.py` — Company model с FK на Sector, enums (SentimentEnum, PositionEnum), все поля из схемы
- [x] `models/financial_report.py` — FinancialReport с extra_metrics JSONB, UNIQUE(company_id, period), PeriodTypeEnum
- [x] `models/dividend.py` — Dividend с DividendStatusEnum, UNIQUE(company_id, record_date)
- [x] `models/catalyst.py` — Catalyst с nullable company_id, CatalystTypeEnum, ImpactEnum, MagnitudeEnum
- [x] `models/price.py` — Price с OHLCV, UNIQUE(company_id, date)
- [x] `models/news.py` — News с двойным nullable FK (company_id, sector_id), ImpactEnum, StrengthEnum
- [x] `models/trade_signal.py` — TradeSignal с FK на news, SignalEnum, DirectionEnum, SignalStatusEnum, confidence DECIMAL
- [x] Написать тесты: создание каждой модели, проверка constraints (unique, FK, nullable)
- [x] Запустить тесты — должны пройти

### Task 3: Alembic — миграции

**Files:**
- Create: `investment-api/alembic.ini`
- Create: `investment-api/alembic/env.py`
- Create: `investment-api/alembic/versions/001_initial.py`

- [x] `alembic init alembic` — инициализация
- [x] Настроить `alembic/env.py` для async SQLAlchemy + подхват моделей из `app.models`
- [x] `alembic revision --autogenerate -m "initial"` — первая миграция (все 8 таблиц)
- [x] `alembic upgrade head` — применить миграцию
- [x] Проверить: все таблицы, индексы, constraints созданы корректно
- [x] Написать тест: `alembic upgrade head` + `alembic downgrade base` проходит без ошибок
- [x] Запустить тесты — должны пройти

### Task 4: Pydantic schemas — request/response модели

**Files:**
- Create: `investment-api/app/schemas/__init__.py`
- Create: `investment-api/app/schemas/sector.py`
- Create: `investment-api/app/schemas/company.py`
- Create: `investment-api/app/schemas/financial_report.py`
- Create: `investment-api/app/schemas/dividend.py`
- Create: `investment-api/app/schemas/catalyst.py`
- Create: `investment-api/app/schemas/price.py`
- Create: `investment-api/app/schemas/news.py`
- Create: `investment-api/app/schemas/trade_signal.py`

- [x] Для каждой сущности: Create, Update (partial), Response схемы
- [x] `CompanyResponse` — включает вложенные списки (последние catalysts, dividends, latest price)
- [x] `CompanyListResponse` — облегчённая версия для списка (без вложенных)
- [x] `CompanyFilter` — query params: sector, sentiment, position, min_upside, max_p_e
- [x] `FinancialReportCreate` — валидация extra_metrics (JSONB, произвольные ключи, значения — числа)
- [x] `TradeSignalCreate` — валидация: confidence 0-100, risk_reward >= 0
- [x] `PriceBulkCreate` — для массовой загрузки цен (список OHLCV записей)
- [x] Написать тесты: валидация Pydantic (корректные данные проходят, невалидные — нет)
- [x] Запустить тесты — должны пройти

### Task 5: CRUD endpoints — Companies + Sectors

**Files:**
- Create: `investment-api/app/api/__init__.py`
- Create: `investment-api/app/api/sectors.py`
- Create: `investment-api/app/api/companies.py`
- Create: `investment-api/app/api/deps.py`

- [x] `api/deps.py` — get_db dependency (async session), API key auth dependency
- [x] `api/sectors.py` — GET /sectors, GET /sectors/{slug}, POST /sectors, PUT /sectors/{slug}
- [x] `api/companies.py` — GET /companies (с фильтрами: sector, sentiment, position, min_upside), GET /companies/{ticker}, POST /companies/{ticker} (upsert), PUT /companies/{ticker}
- [x] `GET /companies/{ticker}` — response включает: company + latest price + active catalysts + last dividend
- [x] Подключить роутеры в `app/main.py`
- [x] Написать тесты: CRUD для sectors, CRUD для companies, фильтры, upsert логика
- [x] Запустить тесты — должны пройти

### Task 6: CRUD endpoints — Financial Reports + Dividends

**Files:**
- Create: `investment-api/app/api/reports.py`
- Create: `investment-api/app/api/dividends.py`

- [x] `api/reports.py` — GET /companies/{ticker}/reports (?period_type=quarterly), POST /companies/{ticker}/reports (upsert by period), GET /companies/{ticker}/reports/latest
- [x] `api/dividends.py` — GET /companies/{ticker}/dividends, POST /companies/{ticker}/dividends, GET /dividends/upcoming (ближайшие отсечки по всем компаниям)
- [x] Написать тесты: CRUD, фильтр по period_type, upsert by period, upcoming dividends
- [x] Запустить тесты — должны пройти

### Task 7: CRUD endpoints — Catalysts + Prices

**Files:**
- Create: `investment-api/app/api/catalysts.py`
- Create: `investment-api/app/api/prices.py`

- [x] `api/catalysts.py` — GET /companies/{ticker}/catalysts (?is_active=true), POST /companies/{ticker}/catalysts, POST /catalysts (макро, без company_id), PUT /catalysts/{id} (деактивация)
- [x] `api/prices.py` — GET /companies/{ticker}/prices (?from=&to=), POST /companies/{ticker}/prices (bulk upsert), GET /companies/{ticker}/prices/latest
- [x] Написать тесты: фильтры, bulk upsert цен, макро-катализаторы без компании
- [x] Запустить тесты — должны пройти

### Task 8: CRUD endpoints — News + Trade Signals

**Files:**
- Create: `investment-api/app/api/news.py`
- Create: `investment-api/app/api/signals.py`

- [x] `api/news.py` — GET /companies/{ticker}/news, GET /sectors/{slug}/news, POST /news (с optional company_id, sector_id), GET /news (?impact=positive&from=)
- [x] `api/signals.py` — GET /companies/{ticker}/signals (?status=active), POST /companies/{ticker}/signals, PUT /signals/{id} (закрытие: status + result_pct + closed_at)
- [x] Написать тесты: фильтры, связь signal↔news, закрытие сигнала с результатом
- [x] Запустить тесты — должны пройти

### Task 9: Серверные jobs — загрузка данных MOEX

**Files:**
- Create: `investment-api/app/jobs/__init__.py`
- Create: `investment-api/app/jobs/fetch_moex.py`
- Create: `investment-api/app/jobs/fetch_prices.py`

- [ ] `jobs/fetch_moex.py` — портировать логику из `download_moex.py`: получение market snapshot → запись в companies (current_price, market_cap, adv, spread)
- [ ] `jobs/fetch_prices.py` — портировать из `update_prices.py`: batch загрузка OHLCV → bulk upsert в prices
- [ ] API endpoints для запуска: POST /jobs/fetch-moex, POST /jobs/fetch-prices (или отдельный internal router)
- [ ] Написать тесты: mock MOEX API responses, проверить парсинг и запись в БД
- [ ] Запустить тесты — должны пройти

### Task 10: Серверные jobs — SmartLab + MOEX Events

**Files:**
- Create: `investment-api/app/jobs/fetch_smartlab.py`
- Create: `investment-api/app/jobs/fetch_events.py`

- [ ] `jobs/fetch_smartlab.py` — портировать из `download_smartlab.py`: парсинг CSV со smart-lab → financial_reports + extra_metrics JSONB
- [ ] `jobs/fetch_events.py` — портировать из `download_moex_events.py`: dividends + IR events → dividends table
- [ ] API endpoints: POST /jobs/fetch-smartlab/{ticker}, POST /jobs/fetch-events/{ticker}
- [ ] Написать тесты: mock HTTP responses, проверить парсинг и запись
- [ ] Запустить тесты — должны пройти

### Task 11: Аналитические endpoints

**Files:**
- Create: `investment-api/app/api/analytics.py`

- [ ] GET /analytics/top-upside?limit=10 — компании с макс. upside (замена scripts/top_upside.py)
- [ ] GET /analytics/screener — комбинированный скринер (sector + sentiment + position + min_upside + max_p_e + min_dividend_yield)
- [ ] GET /analytics/sector-summary — сводка по секторам (средний upside, кол-во bullish/bearish)
- [ ] GET /analytics/overdue — компании, требующие обновления (updated_at + частота → дата следующего обновления)
- [ ] Написать тесты: скринер с разными комбинациями фильтров, пустые результаты
- [ ] Запустить тесты — должны пройти

### Task 12: Скрипт миграции — migrate_all.py

**Files:**
- Create: `investment-analysis/scripts/migrate_all.py`

- [ ] Парсинг YAML frontmatter из всех `companies/*/_index.md` → POST /companies/{ticker}
- [ ] Парсинг `data/catalysts.json` → POST /companies/{ticker}/catalysts
- [ ] Парсинг `data/price_history.csv` → POST /companies/{ticker}/prices (bulk)
- [ ] Парсинг `data/moex_events.json` (dividends) → POST /companies/{ticker}/dividends
- [ ] Парсинг `data/smartlab_quarterly.csv` + `smartlab_yearly.csv` → POST /companies/{ticker}/reports
- [ ] Парсинг `data/news.json` → POST /news
- [ ] Парсинг `data/trade_signals.json` → POST /companies/{ticker}/signals
- [ ] Создание секторов из уникальных sector значений → POST /sectors
- [ ] Отчёт: сколько записей загружено в каждую таблицу, какие ошибки
- [ ] Написать тесты: парсинг одной компании (SBER) — все файлы → корректные API payloads
- [ ] Запустить тесты — должны пройти

### Task 13: Скрипт синхронизации — sync_analysis.py

**Files:**
- Create: `investment-analysis/scripts/sync_analysis.py`

- [ ] Принимает тикер: `python3 scripts/sync_analysis.py SBER`
- [ ] Парсит YAML frontmatter из `companies/SBER/_index.md`
- [ ] PUT /companies/SBER — обновляет sentiment, fair_value, upside, position и т.д.
- [ ] Парсит key_risks/key_opportunities → POST /companies/SBER/catalysts (деактивирует старые, создаёт новые)
- [ ] Если есть `data/news.json` — синхронизирует новые записи → POST /news
- [ ] Если есть `data/trade_signals.json` — синхронизирует → POST /companies/SBER/signals
- [ ] Флаг `--all` — синхронизация всех компаний
- [ ] Написать тесты: парсинг frontmatter, формирование payloads
- [ ] Запустить тесты — должны пройти

### Task 14: Docker deployment + scheduling

**Files:**
- Modify: `investment-api/docker-compose.yml`
- Create: `investment-api/app/jobs/scheduler.py`

- [ ] Добавить scheduling: fetch_prices ежедневно в 19:00 MSK, fetch_moex ежедневно, fetch_events еженедельно
- [ ] Варианты: APScheduler внутри FastAPI, или cron на хосте вызывающий API endpoints
- [ ] Production docker-compose: volumes для postgres, restart policies, environment
- [ ] Healthcheck endpoint: GET /health (проверка DB connection)
- [ ] Написать тесты: healthcheck, scheduler конфигурация
- [ ] Запустить тесты — должны пройти

### Task 15: Verify acceptance criteria

- [ ] Все 8 таблиц созданы и заполнены через миграцию
- [ ] CRUD endpoints работают для всех сущностей
- [ ] Фильтры: GET /companies?sector=finance&sentiment=bullish возвращает корректные данные
- [ ] GET /companies/{ticker} возвращает карточку со всеми вложенными данными
- [ ] Серверные jobs корректно загружают данные с MOEX и SmartLab
- [ ] sync_analysis.py корректно синхронизирует данные из _index.md
- [ ] Запустить полный test suite
- [ ] Проверить: docker compose up → app доступен, postgres с данными

### Task 16: [Final] Documentation

- [ ] README.md для investment-api: setup, API docs (ссылка на /docs), deployment
- [ ] Обновить CLAUDE.md в investment-analysis: описать API-интеграцию и sync_analysis.py
- [ ] Обновить Makefile в investment-analysis: добавить target `sync` для вызова sync_analysis.py
- [ ] Переместить план в `docs/plans/completed/`

## Technical Details

### Enums (PostgreSQL + Python)

```python
class SentimentEnum(str, Enum):
    bullish = "bullish"
    neutral = "neutral"
    bearish = "bearish"

class PositionEnum(str, Enum):
    buy = "buy"
    hold = "hold"
    sell = "sell"
    watch = "watch"
    avoid = "avoid"

class PeriodTypeEnum(str, Enum):
    quarterly = "quarterly"
    yearly = "yearly"
    ltm = "ltm"

class DividendStatusEnum(str, Enum):
    announced = "announced"
    confirmed = "confirmed"
    paid = "paid"

class CatalystTypeEnum(str, Enum):
    opportunity = "opportunity"
    risk = "risk"
    cb_meeting = "cb_meeting"
    event = "event"

class ImpactEnum(str, Enum):
    positive = "positive"
    negative = "negative"
    mixed = "mixed"
    neutral = "neutral"

class MagnitudeEnum(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"

class SignalEnum(str, Enum):
    buy = "buy"
    skip = "skip"

class DirectionEnum(str, Enum):
    long_positive = "long-positive"
    long_oversold = "long-oversold"
    skip = "skip"

class PositionSizeEnum(str, Enum):
    full = "full"
    half = "half"
    skip = "skip"

class SignalStatusEnum(str, Enum):
    active = "active"
    closed = "closed"
    expired = "expired"

class StrengthEnum(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"

class ActionEnum(str, Enum):
    buy = "buy"
    hold = "hold"
    sell = "sell"
```

### extra_metrics JSONB примеры

**Банки:**
```json
{"nim": 6.2, "npl_ratio": 2.1, "cost_income": 28.5, "deposits_bln": 25000, "credits_bln": 22000}
```

**Нефтегаз:**
```json
{"ebitda": 1850, "capex": 520, "fcf": 980, "ev_ebitda": 2.8, "debt_ebitda": 0.3}
```

**Ритейл:**
```json
{"same_store_sales": 12.5, "revenue_per_sqm": 450, "store_count": 22000}
```

### API Auth

Простой API key в заголовке `X-API-Key`. Для MVP достаточно.

```python
async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
```

Read-only endpoints (GET) — без авторизации. Write endpoints (POST/PUT) — с API key.

## Post-Completion

**Manual verification:**
- Проверить API через Swagger UI (/docs) — все endpoints документированы
- Загрузить данные через migrate_all.py — проверить корректность
- Проверить sync_analysis.py после реального обновления _index.md
- Тест под нагрузкой: 73 компании × 365 дней цен = ~26к записей в prices

**External system updates:**
- Настроить DNS / reverse proxy для API на VPS
- Обновить внешние потребители (фронтенд, бот) на новые API endpoints
- Настроить мониторинг (uptime, error rate)
- Настроить бэкапы PostgreSQL на VPS
