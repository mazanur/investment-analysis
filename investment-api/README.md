# Investment API

FastAPI + PostgreSQL backend for investment analysis data.

## Setup

```bash
pip install -e ".[dev]"
docker compose up db -d
uvicorn app.main:app --reload
```

## Tests

```bash
pytest
```

## API Docs

http://localhost:8000/docs
