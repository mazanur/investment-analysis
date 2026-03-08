# Investment API

FastAPI + PostgreSQL backend for storing and querying investment analysis data. Provides a normalized relational database (8 tables) with REST API, automated data jobs (MOEX, SmartLab), and analytics endpoints.

## Quick Start

### Local development

```bash
# 1. Start PostgreSQL
docker compose up db -d

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Copy env and configure
cp .env.example .env

# 4. Run migrations
alembic upgrade head

# 5. Start the app
uvicorn app.main:app --reload
```

The API is available at http://localhost:8000. Interactive docs (Swagger UI) at http://localhost:8000/docs.

### Docker (production)

```bash
# Set API_KEY in environment or .env
export API_KEY=your-secret-key

docker compose up -d
```

This starts both PostgreSQL and the app. The app runs migrations automatically and includes an APScheduler for automated data fetching.

## Configuration

Environment variables (or `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5434/investment` | Async PostgreSQL connection string |
| `API_KEY` | `dev-api-key` | API key for write operations (POST/PUT) |
| `DEBUG` | `true` | Debug mode (auto-creates tables on startup) |

## API Endpoints

### Core CRUD

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/sectors` | - | List all sectors |
| POST | `/sectors` | key | Create sector |
| GET | `/companies` | - | List companies (filterable) |
| GET | `/companies/{ticker}` | - | Company card with nested data |
| POST | `/companies/{ticker}` | key | Upsert company |
| GET | `/companies/{ticker}/reports` | - | Financial reports |
| POST | `/companies/{ticker}/reports` | key | Upsert report |
| GET | `/companies/{ticker}/dividends` | - | Dividends |
| POST | `/companies/{ticker}/dividends` | key | Create dividend |
| GET | `/dividends/upcoming` | - | Upcoming dividends across all companies |
| GET | `/companies/{ticker}/catalysts` | - | Catalysts |
| POST | `/companies/{ticker}/catalysts` | key | Create catalyst |
| POST | `/catalysts` | key | Create macro catalyst (no company) |
| GET | `/companies/{ticker}/prices` | - | Price history |
| POST | `/companies/{ticker}/prices` | key | Bulk upsert prices |

### Company Filters

`GET /companies` supports query parameters:
- `sector` — filter by sector slug
- `sentiment` — bullish / neutral / bearish
- `position` — buy / hold / sell / watch / avoid
- `min_upside` — minimum upside percentage
- `max_p_e` — maximum P/E ratio

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/analytics/top-upside?limit=10` | Companies with highest upside |
| GET | `/analytics/screener` | Combined screener with multiple filters |
| GET | `/analytics/sector-summary` | Sector-level aggregated stats |
| GET | `/analytics/overdue` | Companies needing analysis refresh |

### Data Jobs

All job endpoints require API key authentication.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/jobs/fetch-moex` | Fetch market snapshot from MOEX ISS |
| POST | `/jobs/fetch-prices` | Fetch OHLCV prices from MOEX ISS |
| POST | `/jobs/fetch-smartlab/{ticker}` | Fetch financial reports from smart-lab.ru |
| POST | `/jobs/fetch-events/{ticker}` | Fetch dividends from MOEX ISS |

### Health Check

`GET /health` — returns DB connectivity status (no auth required).

## Authentication

Read-only endpoints (GET) require no authentication. Write endpoints (POST/PUT) require the `X-API-Key` header:

```bash
curl -X POST http://localhost:8000/companies/SBER \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "Sber", "sector_slug": "finance", "sentiment": "bullish"}'
```

## Automated Scheduling

In production mode (`DEBUG=false`), APScheduler runs these jobs automatically:

| Job | Schedule | Description |
|-----|----------|-------------|
| fetch_moex | Mon-Fri 19:00 MSK | Market snapshot |
| fetch_prices | Mon-Fri 19:05 MSK | Daily OHLCV prices |
| fetch_events | Sunday 10:00 MSK | Dividends for all companies |

## Database Schema

8 tables: `sectors`, `companies`, `financial_reports`, `dividends`, `catalysts`, `prices`, `news`, `trade_signals`.

Migrations managed via Alembic:

```bash
# Apply latest migration
alembic upgrade head

# Create new migration after model changes
alembic revision --autogenerate -m "description"

# Rollback
alembic downgrade -1
```

## Data Migration

To populate the database from the investment-analysis workspace:

```bash
# From the investment-analysis root
python3 scripts/migrate_all.py

# Or for a specific ticker
python3 scripts/migrate_all.py --ticker SBER
```

## Tests

```bash
pytest
```

Tests use SQLite (aiosqlite) for speed. No external services required.

## Project Structure

```
investment-api/
├── app/
│   ├── main.py          # FastAPI app, lifespan, router setup
│   ├── config.py         # Pydantic Settings
│   ├── db.py             # Async SQLAlchemy engine + session
│   ├── models/           # SQLAlchemy 2.0 models (8 tables)
│   ├── schemas/          # Pydantic v2 request/response schemas
│   ├── api/              # FastAPI routers (CRUD + analytics + jobs)
│   │   ├── deps.py       # Dependencies (DB session, API key auth)
│   │   └── ...
│   └── jobs/             # Server-side data fetching jobs
│       ├── scheduler.py  # APScheduler configuration
│       └── ...
├── alembic/              # Database migrations
├── tests/                # pytest test suite
├── docker-compose.yml    # PostgreSQL + app
├── Dockerfile
└── pyproject.toml
```

## Author

AlmazNurmukhametov
