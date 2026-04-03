# Sraosha architecture

This document describes how the [`sraosha/`](sraosha) Python package is structured and how the main components interact. For product goals and contributor notes, see [INSTRUCTIONS.md](INSTRUCTIONS.md).

## System context

Sraosha is a **self-hosted** service: a FastAPI application (JSON API + Jinja2 UI), optional **Celery** workers for scheduled jobs, **PostgreSQL** for persistence, and **Redis** as the Celery broker/backend. Contract validation uses **datacontract-cli**. Optional **Soda Core** checks (installed separately) power the data-quality module against configured database connections.

```mermaid
flowchart TB
  subgraph clients [Clients]
    CLI[sraosha_CLI]
    Browser[Browser]
    ExtHTTP[HTTP_clients]
  end
  subgraph processes [Processes]
    API[FastAPI_sraosha_serve]
    Worker[Celery_worker]
    Beat[Celery_beat]
  end
  subgraph stores [Data_stores]
    PG[(PostgreSQL)]
    Redis[(Redis)]
  end
  subgraph external [External_at_runtime]
    DC[datacontract-cli]
    Soda[Soda_Core_optional]
    DS[(Customer_datasets)]
  end
  CLI --> API
  Browser --> API
  ExtHTTP --> API
  API --> PG
  API --> DC
  Worker --> PG
  Worker --> Redis
  Worker --> Soda
  Soda --> DS
  Beat --> Redis
```

## Validation path

The [`ContractEngine`](sraosha/core/engine.py) loads YAML via [`ContractLoader`](sraosha/core/loader.py), runs [`ContractRunner`](sraosha/core/runner.py) (datacontract-cli), builds a [`ValidationResult`](sraosha/core/engine.py), and optionally persists a [`ValidationRun`](sraosha/models/run.py) when a DB session is provided. `block` enforcement raises [`ContractViolationError`](sraosha/core/engine.py) on failure.

```mermaid
sequenceDiagram
  participant Caller as Caller_CLI_API_or_embedded
  participant Engine as ContractEngine
  participant Loader as ContractLoader
  participant Runner as ContractRunner
  participant DC as datacontract-cli
  participant DB as PostgreSQL
  Caller->>Engine: run
  Engine->>Loader: load_contract
  Loader-->>Engine: contract_dict
  Engine->>Runner: run
  Runner->>DC: validate
  DC-->>Runner: raw_result
  Runner-->>Engine: normalized_dict
  Engine->>Engine: ValidationResult
  opt db_session_set
    Engine->>DB: insert ValidationRun
  end
  alt block_and_failed
    Engine-->>Caller: ContractViolationError
  else else
    Engine-->>Caller: ValidationResult
  end
```

## HTTP API and dashboard

[`create_app()`](sraosha/api/app.py) mounts routers under `/api/v1` and HTML under `/ui`. `/` redirects to `/ui/`. OpenAPI is at `/docs` and `/redoc`.

| Prefix | Router module | Purpose |
|--------|----------------|---------|
| `/api/v1/teams` | [`teams`](sraosha/api/routers/teams.py) | Teams and compliance ownership |
| `/api/v1/alerting-profiles` | [`alerting_profiles`](sraosha/api/routers/alerting_profiles.py) | Notification profiles |
| `/api/v1/contracts` | [`contracts`](sraosha/api/routers/contracts.py) | Contract CRUD and validation triggers |
| `/api/v1/runs` | [`runs`](sraosha/api/routers/runs.py) | Validation run history |
| `/api/v1/compliance` | [`compliance`](sraosha/api/routers/compliance.py) | Team scores and trends |
| `/api/v1/impact` | [`impact`](sraosha/api/routers/impact.py) | Dependency graph and impact analysis |
| `/api/v1/schedules` | [`schedules`](sraosha/api/routers/schedules.py) | Validation schedules |
| `/api/v1/data-quality` | [`data_quality`](sraosha/api/routers/data_quality.py) | DQ checks and runs (Soda) |
| `/ui` | [`dashboard`](sraosha/api/routers/dashboard.py) | Jinja2 dashboard |

Optional API authentication: if `API_KEY` is set in settings, routes using [`verify_api_key`](sraosha/api/deps.py) require the `X-API-Key` header.

## Celery topology

Use **one** Celery **beat** process (periodic scheduler) and **one or more** **worker** processes. Docker Compose maps this to `beat` and `worker` services. CLI entrypoints: [`sraosha worker`](sraosha/cli/main.py) and [`sraosha beat`](sraosha/cli/main.py).

Periodic tasks are defined in [`celery_app.py`](sraosha/tasks/celery_app.py):

| Beat key | Task | Schedule |
|----------|------|----------|
| `compliance-compute-daily` | `sraosha.tasks.compliance_compute.compute_compliance_scores` | Daily |
| `check-validation-schedules` | `sraosha.tasks.validation_scheduler.check_validation_schedules` | Every 60 seconds |
| `check-dq-schedules` | `sraosha.tasks.dq_scheduler.check_dq_schedules` | Every 60 seconds |

## Data quality (Soda)

[`sraosha/dq/`](sraosha/dq/) integrates **Soda Core** lazily: connectors are optional extras. DQ checks are stored per team/connection; runs are executed via Celery ([`dq_scan`](sraosha/tasks/dq_scan.py)) and exposed under `/api/v1/data-quality`. This is separate from datacontract-cli validation but complements it for database-native checks.

## Impact analysis

[`sraosha/impact/`](sraosha/impact/) builds a directed graph (NetworkX) from contract metadata and supports “what breaks if these fields change?” analysis via the impact API and `/ui/impact`.

## Compliance scoring

[`compliance/scoring.py`](sraosha/compliance/scoring.py) provides pure helpers for rolling windows and score math. [`compute_compliance_scores`](sraosha/tasks/compliance_compute.py) aggregates validation runs per team into `compliance_scores`.

## Package map

| Path | Role |
|------|------|
| [`sraosha/core/`](sraosha/core/) | Contract loading, validation runner, credentials resolution |
| [`sraosha/api/`](sraosha/api/) | FastAPI app, routers, Jinja2 templates, contract YAML helpers |
| [`sraosha/models/`](sraosha/models/) | SQLAlchemy models |
| [`sraosha/schemas/`](sraosha/schemas/) | Pydantic request/response models |
| [`sraosha/dq/`](sraosha/dq/) | Soda-backed DQ runner and check configuration |
| [`sraosha/impact/`](sraosha/impact/) | Graph and impact analyzer |
| [`sraosha/compliance/`](sraosha/compliance/) | Score helpers |
| [`sraosha/alerting/`](sraosha/alerting/) | Slack, email, dispatch |
| [`sraosha/tasks/`](sraosha/tasks/) | Celery app and task modules |
| [`sraosha/cli/`](sraosha/cli/) | Typer CLI |
| [`sraosha/db.py`](sraosha/db.py) | Async SQLAlchemy engine and session factory |
| [`sraosha/config.py`](sraosha/config.py) | `SraoshaSettings` and config file resolution |

## Database migrations

Schema changes are managed with **Alembic**. The CLI command `sraosha db` runs `alembic upgrade head` (see [`cli/main.py`](sraosha/cli/main.py)).
