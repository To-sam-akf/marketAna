# MarketANA

MarketANA is a front-end/back-end separated project for futures market article
analysis. This repository currently implements the pn01 technical baseline:
FastAPI backend skeleton, Vue 3 + Vite frontend skeleton, MySQL connection
foundation, scheduler wiring, unified configuration, logging, response shape,
and baseline tests.

## Project Layout

```text
back_end/app/
  api/             FastAPI routes
  core/            config, database, logging, responses, exceptions, statuses
  models/          SQLAlchemy models added in later phases
  repositories/    data access layer
  services/        business services and external clients
  tasks/           scheduler and background task wiring
front_end/         Vue 3 + Vite frontend
tests/             backend baseline tests
```

## Backend Setup

The backend uses Python 3.11 and `uv`.

```sh
uv sync
uv run uvicorn back_end.app.main:app --reload
```

Health check:

```sh
curl http://127.0.0.1:8000/health
```

Expected response shape:

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "status": "ok",
    "database": "unconfigured"
  }
}
```

`database` becomes `ok` after a valid MySQL `DATABASE_URL` is configured.

## Configuration

Copy `.env.example` to `.env` for local development. `.env` is ignored by Git.

```sh
cp .env.example .env
```

Important settings:

- `DATABASE_URL`: MySQL SQLAlchemy URL, for example
  `mysql+pymysql://user:password@127.0.0.1:3306/marketana?charset=utf8mb4`
- `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`: reserved for later LLM phases
- `TASK_BATCH_SIZE`: scheduler batch size, default `20`
- `RULE_CONFIDENCE_THRESHOLD`: rule engine threshold, default `0.7`
- `SCHEDULER_POLL_INTERVAL_SECONDS`: scheduler interval, default `300`
- `LOG_LEVEL`: backend log level, default `INFO`

## Frontend Setup

Frontend dependencies are managed inside `front_end`.

```sh
cd front_end
npm install
npm run dev
```

Build and type-check:

```sh
cd front_end
npm run build
npm run type-check
```

## Tests

```sh
uv run pytest
```

The pn01 tests cover:

- `/health` response format
- article processing status constants: `-1, 0, 1, 2, 3, 4, 5`
- default configuration loading
- database health behavior when MySQL is not configured

## Article Processing Status

The backend status constants are:

- `-1`: failed
- `0`: pending
- `1`: parsed
- `2`: cleaned
- `3`: rule analyzed
- `4`: LLM inferred
- `5`: stored
