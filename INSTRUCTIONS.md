# Sraosha — Project specification

> **For AI coding assistants:** Product goals and positioning live here. **Authoritative technical structure** is in [ARCHITECTURE.md](ARCHITECTURE.md) and the [`sraosha/`](sraosha) package. Do not assume older phase plans or speculative features (for example a separate React app or a drift submodule) unless you find matching code in the repository.

---

## Table of Contents

1. [Project overview](#1-project-overview)
2. [Problem statement](#2-problem-statement)
3. [Positioning and differentiation](#3-positioning-and-differentiation)
4. [Current implementation](#4-current-implementation)
5. [Tech stack](#5-tech-stack)
6. [Repository layout](#6-repository-layout)
7. [Integration surface](#7-integration-surface)
8. [Configuration](#8-configuration)
9. [Data contract format](#9-data-contract-format)
10. [API overview](#10-api-overview)
11. [Testing](#11-testing)
12. [Docker and deployment](#12-docker-and-deployment)
13. [Notes for contributors](#13-notes-for-contributors)

---

## 1. Project overview

**Name:** Sraosha  
**Tagline:** The enforcement and governance runtime for data contracts.  
**Type:** Open-source Python project (MIT license)  
**Language:** Python 3.11+ (FastAPI, SQLAlchemy async, Jinja2 templates for the UI)  
**Target users:** Data Engineers, Data Platform teams, Analytics Engineers

Sraosha is **not** a replacement for `datacontract-cli`. It is a governance runtime that wraps `datacontract-cli` as its validation engine and adds:

- Enforcing contracts from the CLI, API, or embedded `ContractEngine`
- Optional **Soda Core**–based data quality checks against configured database connections (complementary to contract YAML checks)
- Mapping cross-contract impact when a schema change is proposed
- Tracking compliance history over time with team-level scoring
- A self-hosted web dashboard (Jinja2, same process as the API)

---

## 2. Problem statement

### What `datacontract-cli` already solves

- Defining contracts in YAML (ODCS format)
- Running schema and quality tests on-demand
- Exporting contracts to various formats (dbt, SQL, Avro, etc.)
- Linting and validating contract YAML files

### What it does not solve (Sraosha’s territory)

| Gap | Impact |
|-----|--------|
| No built-in enforcement runtime | Pipelines and jobs do not automatically block on violations without glue code |
| No cross-contract awareness | Changing one contract has unknown downstream effects |
| No compliance history | Hard to track reliability trends by team |
| No centralized governance UI | No single place for contract health across the org |
| No unified alerting hooks | Violations may surface late without integration work |

---

## 3. Positioning and differentiation

### vs. `datacontract-cli`

Sraosha **uses** `datacontract-cli` as a dependency and calls it from [`ContractRunner`](sraosha/core/runner.py). Complementary, not competitive.

### vs. Monte Carlo / Bigeye

Those are often cloud-first SaaS tools. Sraosha is self-hosted, open-source, and contract-first.

### vs. Great Expectations / Soda alone

Those frameworks excel at data quality rules. Sraosha is **governance-first**: it enforces producer–consumer agreements via contracts and persistence. Soda is used **optionally** inside Sraosha for additional DB checks where you install `soda-core` and connectors.

### Positioning statement

> "Sraosha is to data contracts what GitHub Actions is to code — the enforcement and observability runtime, not the authoring tool."

---

## 4. Current implementation

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for:

- System context diagram (API, workers, PostgreSQL, Redis)
- Validation sequence (`ContractEngine` → datacontract-cli)
- HTTP route prefixes and Celery beat schedule
- Package directory map

**Summary:** FastAPI exposes `/api/v1/*` JSON and `/ui` HTML; PostgreSQL persists state; Redis backs Celery; one beat process plus one or more workers runs scheduled compliance, validation, and DQ tasks.

---

## 5. Tech stack

| Layer | Technology | Notes |
|-------|------------|--------|
| Language | Python 3.11+ | Required |
| Contract validation | datacontract-cli | Via [`ContractRunner`](sraosha/core/runner.py) |
| Optional DQ | Soda Core (+ connectors) | Lazy import in [`sraosha/dq/`](sraosha/dq/) |
| Database | PostgreSQL | Async SQLAlchemy + Alembic |
| API | FastAPI | OpenAPI at `/docs` |
| UI | Jinja2 | Templates under [`sraosha/api/templates/`](sraosha/api/templates/) |
| Task queue | Celery + Redis | [`sraosha/tasks/celery_app.py`](sraosha/tasks/celery_app.py) |
| Graphs | NetworkX | Impact analysis |
| CLI | Typer | [`sraosha/cli/main.py`](sraosha/cli/main.py) |

---

## 6. Repository layout

High-level layout (see [ARCHITECTURE.md](ARCHITECTURE.md) for module responsibilities):

```
sraosha/
├── sraosha/
│   ├── api/            # FastAPI app, routers, Jinja2 templates
│   ├── alerting/
│   ├── cli/
│   ├── compliance/
│   ├── core/           # Engine, loader, runner, credentials
│   ├── dq/               # Soda-backed data quality
│   ├── impact/
│   ├── models/
│   ├── schemas/
│   └── tasks/            # Celery tasks
├── alembic/
├── tests/
├── examples/
├── pyproject.toml
├── ARCHITECTURE.md
└── README.md
```

---

## 7. Integration surface

Sraosha does **not** ship orchestrator-specific plugins. Integrate by:

- **CLI:** `sraosha run --contract <path> [--mode block|warn|log]`
- **API:** HTTP endpoints under `/api/v1` (see [ARCHITECTURE.md](ARCHITECTURE.md))
- **Python:** instantiate `ContractEngine` from `sraosha.core.engine` (see [`examples/standalone_example.py`](examples/standalone_example.py))

Orchestrators (Airflow, dbt, Prefect, CI) should invoke one of the above from a task, script, or container.

---

## 8. Configuration

Runtime settings are defined in [`sraosha/config.py`](sraosha/config.py) as `SraoshaSettings`. Configuration is loaded from a `.sraosha` file (dotenv format) when present, with resolution order documented in [README.md](README.md). Environment variables override file values.

Notable fields: `DATABASE_URL`, `REDIS_URL`, `API_HOST`, `API_PORT`, `API_KEY` (optional), alerting and SMTP settings, `ENCRYPTION_KEY` for stored credentials.

---

## 9. Data contract format

Sraosha uses the **Open Data Contract Standard (ODCS)** YAML consumed by `datacontract-cli`.

Optional extension key **`x-sraosha`** is used for governance metadata (for example `enforcement_mode`, team linkage, server connection references). See [`sraosha/core/engine.py`](sraosha/core/engine.py) and [`sraosha/api/contract_yaml.py`](sraosha/api/contract_yaml.py) for how fields are interpreted.

Example skeleton:

```yaml
dataContractSpecification: 1.1.0
id: orders-v1
info:
  title: Orders
  version: 1.0.0

servers:
  production:
    type: postgres
    # ...

models:
  orders:
    type: table
    fields:
      order_id:
        type: text
        required: true

x-sraosha:
  enforcement_mode: block   # block | warn | log
```

A minimal fixture lives at [`tests/fixtures/sample_contract.yaml`](tests/fixtures/sample_contract.yaml).

---

## 10. API overview

JSON API prefixes (see [ARCHITECTURE.md](ARCHITECTURE.md) for the full table):

| Prefix | Area |
|--------|------|
| `/api/v1/teams` | Teams |
| `/api/v1/alerting-profiles` | Alerting profiles |
| `/api/v1/contracts` | Contracts |
| `/api/v1/runs` | Validation runs |
| `/api/v1/compliance` | Compliance scores |
| `/api/v1/impact` | Impact graph and analysis |
| `/api/v1/schedules` | Validation schedules |
| `/api/v1/data-quality` | DQ checks and runs |

Interactive docs: `/docs` on a running server.

---

## 11. Testing

- **Unit tests:** `pytest` under `tests/` (see [`pyproject.toml`](pyproject.toml) `tool.pytest.ini_options`).
- **Integration tests** may require PostgreSQL or other services; see test layout and CI configuration.

```bash
uv run pytest tests/unit/ -v
uv run pytest tests/ -v
```

---

## 12. Docker and deployment

[`docker-compose.yml`](docker-compose.yml) defines PostgreSQL, Redis, the API (`sraosha db` then `sraosha serve`), a Celery worker, and Celery beat. Build context uses the root [`Dockerfile`](Dockerfile).

For one-off tasks (example: compliance recompute), see [README.md](README.md).

---

## 13. Notes for contributors

1. Prefer **async** database access in the API layer; Celery tasks use synchronous DB helpers where appropriate.
2. Use **type hints** and **Pydantic** models for API shapes.
3. Do not hardcode secrets; use `SraoshaSettings`.
4. When changing behavior, update **README.md** or **ARCHITECTURE.md** if users or integrators are affected.
5. The **`datacontract-cli` SDK** is the validation engine; do not reimplement its contract tests.
