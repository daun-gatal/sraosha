# Sraosha

**Enforcement and governance runtime for YAML data contracts.** Validates with [`datacontract-cli`](https://github.com/datacontract/datacontract-cli), exposes a **REST API**, an **operator CLI** (`serve`, `db`, `worker`, `beat`), optional Soda-based database checks, and a **React SPA** served from the API at `/app/` (bundled under `sraosha/web/dist` in the wheel, or `frontend/dist` in a dev checkout).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)

## Contents

- [Features](#features)
- [Install](#install)
- [Quickstart](#quickstart)
- [How it works](#how-it-works)
- [Architecture](#architecture)
- [CLI](#cli)
- [Configuration](#configuration)
- [Development](#development)
- [Contributing & license](#contributing--license)

## Features

| Area | Notes |
|------|--------|
| Contract validation | YAML contracts; engine wraps `datacontract-cli` |
| Enforcement | REST API, Celery schedules, or embed [`ContractEngine`](sraosha/core/engine.py) |
| Connections | Encrypted DB credentials via `/api/v1/connections` for validation and DQ |
| Data quality (optional) | Soda Core checks per connection; install e.g. `soda-core-postgres` as needed |
| Operations | PostgreSQL persistence, Celery + Redis for validation and DQ schedules |
| UI | SPA at `/app/` (included in `pip install`; dev: `make sync-web-dist` or build in `frontend/`), OpenAPI at `/docs` |

## Install

```bash
pip install sraosha
```

Dev extras (tests, lint, types): `pip install -e ".[dev]"`

**Data quality (Soda Core):** contract validation works without Soda. Install Soda only when you want to run DQ scans—**same Python environment** as the API and any **Celery workers** that execute `dq_scan` (packages are not declared in this project; pick versions for your stack):

```bash
pip install soda-core soda-core-postgres   # example: Postgres
```

For containers, add equivalent `pip install` lines to your image Dockerfile.

**Celery:** DQ scans run in the worker process. After changing code that affects Soda or MySQL connections, restart the worker (`make stop && make start`, or `uv run sraosha worker` if you run workers separately) so `dq_scan` loads the update.

**Schema introspection:** PyMySQL (MySQL / ClickHouse wire) and a current **DuckDB** wheel are included for table/column discovery. **Soda DQ** still needs `pip install soda-core soda-core-<connector>`; common driver libraries (`mysql-connector-python`, `trino`, `oracledb`, `pyodbc`, `boto3`, BigQuery/Snowflake/Athena/Azure clients, etc.) are core dependencies so missing sub-dependencies are rarer.

**MySQL / ClickHouse (Soda):** In the connection **Advanced JSON** (`extra_params`), you can set `charset`, `use_unicode`, `collation`, and `use_pure`. They are merged into the Soda YAML and applied during DQ scans. The runner defaults to `charset=utf8mb4` and **`use_pure=true`** (pure-Python connector); the C extension default can still trigger legacy `utf8` errors on some servers.

**Note:** `soda-core-duckdb` 3.5.x expects an older DuckDB (below 1.1), while sraosha pins a newer DuckDB for Python 3.13+ wheels. If you need that exact Soda connector, use a separate venv or Python 3.11 where compatible builds exist.

## Quickstart

**Local development (no Docker)** — install PostgreSQL and Redis yourself, then:

```bash
cp .sraosha.example .sraosha   # point DATABASE_URL and REDIS_URL at your local services
make sync && make db
make start    # builds SPA; starts API (serves UI), Celery worker, and beat in background — logs .sraosha-start-*.log
# make stop   # stops those PIDs plus anything on :8000 / :5173 (e.g. stray Vite)
```

Foreground API only (no worker/beat): `make serve`. Vite on :5173: `make frontend`. Celery alone: `uv run sraosha worker` / `uv run sraosha beat` (with Redis from `.sraosha`).

UI when using `make serve`: `http://localhost:8000/app/` (`make sync-web-dist` builds the SPA into `sraosha/web/dist` and `frontend/dist`).

**Docker Compose (API + built UI):** the [`Dockerfile`](Dockerfile) runs `npm run build` in a Node stage and copies the build into `sraosha/web/dist` in the image. The **`api`** service is the only HTTP entrypoint; it serves the React app under **`/app/`** (and `/` redirects there when the SPA is present). There is no separate frontend container.

```bash
cp .sraosha.example .sraosha   # ensure env matches compose (compose overrides DATABASE_URL / REDIS_URL)
docker compose up --build      # builds the image including the UI, starts postgres, redis, api, worker, beat
# UI: http://localhost:8000/app/   ·   API docs: http://localhost:8000/docs
```

[`docker-compose.yml`](docker-compose.yml) is not wired into the Makefile.

**Local CLI:**

```bash
pip install sraosha
cp .sraosha.example .sraosha
sraosha serve
```

Config path: `sraosha --config /path/to/.sraosha serve` or `SRAOSHA_CONFIG=/path/to/.sraosha`.

**Register and validate** via the API (`POST /api/v1/contracts`) or the UI at `/app/` once the server is running.

## How it works

- **Validation:** the REST API, Celery-triggered runs, or embedded `ContractEngine` run checks via `datacontract-cli`. With `block` mode, failed checks surface as API errors where applicable; results persist when a database is configured.
- **Background:** Celery beat drives periodic jobs (validation and DQ schedule polling); workers execute them. Details: [ARCHITECTURE.md](ARCHITECTURE.md).
- **Data quality:** Optional Soda checks are configured per connection (`/api/v1/data-quality`); they sit alongside contract validation.

Lineage nodes include a **platform** string from contract `servers.*.type` for display.

## Architecture

- **FastAPI:** JSON `/api/v1/*`, SPA `/app/*` when built.
- **PostgreSQL:** Contracts, runs, teams, schedules, DQ metadata.
- **Redis:** Celery broker; production uses one `sraosha beat` and one or more `sraosha worker` processes.

```
REST API / UI / Celery
        → ContractEngine → datacontract-cli
        → PostgreSQL
FastAPI (:8000)  +  Celery workers
```

More diagrams and layout: **[ARCHITECTURE.md](ARCHITECTURE.md)**.

## CLI

```bash
sraosha [--config PATH] <command>

sraosha serve [--host 0.0.0.0] [--port 8000] [--reload]
sraosha db
sraosha worker [--loglevel info] [--concurrency 4] [--hostname worker@%h]
sraosha beat [--loglevel info]
sraosha version
```

## Configuration

Dotenv-style **`.sraosha`**: copy [`.sraosha.example`](.sraosha.example) — it lists every **`SraoshaSettings`** field from [`sraosha/config.py`](sraosha/config.py) (same names as env vars). Resolution: `--config`, `SRAOSHA_CONFIG`, `./.sraosha`, `~/.sraosha`. Env vars override the file.

**OpenAPI / typed clients:** schema is at `/openapi.json` (same host as the API). Example: `npx openapi-typescript http://localhost:8000/openapi.json -o ./src/api/schema.d.ts` from your frontend repo.

## Development

Use **`make help`** for commands. Typical flow: `make sync`, `make db`, then **`make start`** (or `make serve` if you only need the API + built UI). See [Quickstart](#quickstart).

```bash
uv sync --extra dev    # or: pip install -e ".[dev]"
pre-commit install
make db && make start
```

**Make:** `sync`, `sync-web-dist`, `db`, `start`, `stop`, `serve`, `frontend`, `lint`, `fix`, `test`, `clean` — see [`Makefile`](Makefile). Full guide: [CONTRIBUTING.md](CONTRIBUTING.md).

## Contributing & license

See [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under MIT — [LICENSE](LICENSE).
