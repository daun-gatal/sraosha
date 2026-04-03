# Sraosha

**Enforcement and governance runtime for YAML data contracts.** Validates with [`datacontract-cli`](https://github.com/datacontract/datacontract-cli), exposes CLI and API enforcement, optional Soda-based database checks, cross-contract impact analysis, compliance tracking, and a self-hosted dashboard (Jinja2 + FastAPI) on the API port.

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
| Enforcement | CLI, HTTP API, or embed [`ContractEngine`](sraosha/core/engine.py) |
| Data quality (optional) | Soda Core checks per connection; install e.g. `soda-core-postgres` as needed |
| Impact | Dependency graph, lineage UI (`/ui/impact`), `GET /api/v1/impact/graph` and lineage endpoints |
| Operations | PostgreSQL persistence, Celery + Redis for schedules and compliance snapshots |
| UI | Dashboard under `/ui/*`, OpenAPI at `/docs` |

## Install

```bash
pip install sraosha
```

Dev extras (tests, lint, types): `pip install -e ".[dev]"`

## Quickstart

**Docker Compose** (API, PostgreSQL, Redis, Celery worker and beat):

```bash
cp .sraosha.example .sraosha   # edit as needed
docker compose up -d
# Dashboard: http://localhost:8000/ui/
```

**Local CLI:**

```bash
pip install sraosha
cp .sraosha.example .sraosha
sraosha serve
```

Config path: `sraosha --config /path/to/.sraosha serve` or `SRAOSHA_CONFIG=/path/to/.sraosha`.

**Register and validate:**

```bash
sraosha register --contract contracts/orders.yaml --team my-team
sraosha run --contract contracts/orders.yaml --mode block
```

## How it works

- **Validation:** `sraosha run`, the REST API, or `ContractEngine` run checks via `datacontract-cli`. With `block` mode, failures exit non-zero (CLI) or raise (library); results persist when a database is configured.
- **Background:** Celery beat drives periodic jobs (compliance recompute, validation and DQ schedule polling); workers execute them. Details: [ARCHITECTURE.md](ARCHITECTURE.md).
- **Data quality:** Optional Soda checks are configured per connection (`/api/v1/data-quality`); they sit alongside contract validation.

Lineage nodes include a **platform** string from contract `servers.*.type` for display.

## Architecture

- **FastAPI:** JSON `/api/v1/*`, dashboard `/ui/*`.
- **PostgreSQL:** Contracts, runs, teams, schedules, DQ metadata, compliance scores.
- **Redis:** Celery broker; production uses one `sraosha beat` and one or more `sraosha worker` processes.

```
Orchestrator / CLI / API
        → ContractEngine → datacontract-cli
        → PostgreSQL
FastAPI (:8000)  +  Celery workers
```

More diagrams and layout: **[ARCHITECTURE.md](ARCHITECTURE.md)**.

## CLI

```bash
sraosha [--config PATH] <command>

sraosha run --contract path/to/contract.yaml [--mode block|warn|log] [--server NAME]
sraosha status [--format table|json]
sraosha history --contract <contract_id> [--limit 20]
sraosha register --contract path/to/contract.yaml --team my-team
sraosha impact --contract <contract_id> --fields field_a,field_b
sraosha serve [--host 0.0.0.0] [--port 8000] [--reload]
sraosha db
sraosha worker [--loglevel info] [--concurrency 4] [--hostname worker@%h]
sraosha beat [--loglevel info]
sraosha version
```

**One-off compliance recompute (Compose):**

```bash
docker compose exec worker celery -A sraosha.tasks.celery_app call \
  sraosha.tasks.compliance_compute.compute_compliance_scores
```

## Configuration

Dotenv-style `.sraosha` file. Resolution (first wins): `--config`, `SRAOSHA_CONFIG`, `./.sraosha`, `~/.sraosha`, then defaults. Environment variables override file values. See `.sraosha.example`.

## Development

```bash
uv sync --extra dev    # or: python -m venv .venv && pip install -e ".[dev]"
pre-commit install
docker compose up postgres redis -d
uv run sraosha db
uv run sraosha serve --reload
```

**Make:** `lint`, `format`, `test`, `test-cov`, `typecheck`, `dev`, `clean` (see `Makefile`). Full guide: [CONTRIBUTING.md](CONTRIBUTING.md).

## Contributing & license

See [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under MIT — [LICENSE](LICENSE).
