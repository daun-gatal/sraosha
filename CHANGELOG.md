# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.2.0] - 2026-04-05

### Added

- **React SPA** in `frontend/` (Bun + Vite), built into `frontend/dist` and served by FastAPI under `/app/` with [`spa`](sraosha/api/spa.py); `/` redirects to `/app/` when the build is present.
- **Connections API** at `/api/v1/connections` ([`connections`](sraosha/api/routers/connections.py)) for stored database credentials used by validation and DQ.
- **Centralized HTTP exception handling** via [`error_handlers`](sraosha/api/error_handlers.py) (consistent JSON errors and CORS behavior).
- **DQ layer refactor**: [`factory`](sraosha/dq/factory.py), [`protocol`](sraosha/dq/protocol.py), [`backends/`](sraosha/dq/backends/), [`result`](sraosha/dq/result.py) for pluggable Soda-backed execution.
- **Shared domain helpers** under [`services/`](sraosha/services/) and introspection-related schemas where applicable.
- **CI** job to install, lint, and build the frontend with **Bun** (runs after Python lint).
- **Alembic** migration `002` to drop `compliance_scores` when upgrading from earlier schemas.

### Changed

- **API surface** is JSON + OpenAPI (`/docs`, `/redoc`) plus the SPA; operational workflows use the UI or HTTP clients directly.
- **Docker image** builds the UI in a **Node** stage and copies `frontend/dist` into the Python image (single container for API + static assets).
- **Persistence** no longer includes team compliance scores; focus is contracts, runs, teams, schedules, connections, DQ metadata, and alerts.

### Removed

- **Team compliance scoring** (API, models, Celery `compute_compliance_scores` task, and related modules); `compliance_scores` table removed by migration `002`.
- **Impact and lineage** (packages, graph/analyze API, and dashboard views).
- **Jinja2 server-rendered UI** (`/ui`, template tree under `sraosha/api/templates/`).
- **CLI commands** `run`, `register`, `status`, `history`, and `impact`; the CLI now exposes `serve`, `worker`, `beat`, `db`, and `version` only ([`cli/main`](sraosha/cli/main.py)).
- **Demo seed scripts** under `scripts/` and tests tied to removed features.

## [v0.1.2] - 2026-04-03

### Changed

- **Alembic** migrations and `alembic.ini` live under the `sraosha` package; `sraosha db` resolves the config from the installed package path (works from site-packages and Docker).
- **Dockerfile** copies only `sraosha/` (no separate root `alembic/` copy); migrations ship with the wheel.
- **CI / Release** workflows: Docker image rebuild detection now relies on the `sraosha/` prefix for Alembic paths (removed obsolete root `alembic/` / `alembic.ini` patterns).

### Removed

- **`INSTRUCTIONS.md`** — superseded by [ARCHITECTURE.md](ARCHITECTURE.md) and [README.md](README.md).

## [v0.1.1] - 2026-04-03

### Changed

- Bump release to **0.1.1** for PyPI (uploaded artifacts cannot be overwritten at the same version).
- CI workflow allows overlapping runs on a branch (removed concurrency cancellation).

## [v0.1.0] - 2026-04-03

Initial release of **Sraosha**: a self-hosted governance runtime around [datacontract-cli](https://github.com/datacontract/datacontract-cli) for validating data contracts, persisting runs, scoring team compliance, analyzing cross-contract impact, and operating a small dashboard beside the API. Orchestration is **bring-your-own** (CLI, HTTP API, or embedded `ContractEngine` in your jobs); there are no bundled Airflow or dbt operators.

### Added

#### Core validation

- **`ContractEngine`** with enforcement modes `block`, `warn`, and `log`; integrates **`datacontract-cli`** for execution and can persist runs when a database session is available.
- **`ContractLoader`**: load contract YAML from a **local path**, **HTTP(S) URL**, or **Git repository** (Git clone path uses optional `gitpython`; install separately if needed).
- **`ContractRunner`** / **`ContractViolationError`** for CLI and programmatic use with clear pass/fail semantics.

#### HTTP API and UI

- **FastAPI** application with OpenAPI at `/docs` and `/redoc`; JSON API under `/api/v1` for **teams**, **alerting profiles**, **contracts**, **runs**, **compliance**, **impact** (graph, lineage, analyze), **schedules**, and **data quality** endpoints.
- **Jinja2 dashboard** under `/ui` (root `/` redirects to `/ui/`): contract and operational views aligned with the API.
- **CORS** enabled for browser access during development and integration.

#### CLI (`sraosha`)

- `run` — validate a contract (`--contract`, `--mode`, optional `--server`).
- `register` — register a contract with the API and assign an owner team (`--team`).
- `status` / `history` — list registered contracts and run history via the API (`table` or `json`).
- `impact` — call the impact API for a contract and comma-separated changed fields.
- `serve` — run **uvicorn** with the FastAPI app factory (`--host`, `--port`, `--reload`).
- `worker` / `beat` — **Celery** worker and beat (Redis broker/backend from config).
- `db` — **Alembic** `upgrade head` against `alembic.ini`.
- `version` — print package version.
- Global `--config` / `SRAOSHA_CONFIG` for `.sraosha` (dotenv-style) settings.

#### Impact and lineage

- **Dependency graph** built from registered contracts (**NetworkX**), with **impact analysis** for proposed field changes (direct and transitive dependents, severity).
- REST endpoints for **full graph**, **lineage subgraph** (upstream/downstream depth), and **analyze**; dashboard **Lineage** page for exploration.

#### Compliance and scheduling

- **Team-level compliance** scores over a **rolling 30-day** window from run outcomes; stored and surfaced via API and dashboard.
- **Celery** task `compute_compliance_scores` on a **daily** beat schedule.
- **Validation schedules** and **DQ schedules** polled every **60 seconds** from Celery beat, driving on-time contract validation and optional DQ scans per cron-style definitions (**croniter**).

#### Data quality (optional)

- **Soda Core** integration for database checks: lazy import with clear install hints; **DQ runner**, connection metadata, check templates, and API surface under `/api/v1/data-quality`. Requires separate install of `soda-core` and the right DB connector (not pulled in by the base `sraosha` package).

#### Alerting

- **Slack** (incoming webhook) and **SMTP email** channels; **alerting profiles** linked to teams/contracts and dispatched from the alerting layer.

#### Persistence and configuration

- **PostgreSQL** via **SQLAlchemy 2 async** (`asyncpg`); models for contracts, runs, teams, schedules, compliance scores, connections, DQ metadata, alerts, etc.
- **Alembic** migrations shipped with the repo (`sraosha db`).
- **Connection credentials** stored and **decrypted** for use with validation/DQ (`cryptography`); mapping from contract `servers` / `x-sraosha` connection refs.
- **Pydantic Settings** (`SraoshaSettings`): database URL, Redis URL, API bind, optional **API key**, Slack/SMTP toggles and secrets, paths, and related defaults.

#### Packaging and operations

- **`pip install sraosha`** (hatchling build); Python **3.11+**.
- **Dockerfile** and **Docker Compose** recipe for API, PostgreSQL, Redis, worker, and beat for local or server deployments.
- **GitHub Actions**: CI on pull requests (lint, type check, tests, package build, optional PR Docker build when relevant paths change, **Grype** supply-chain scan); **Release** workflow on `main` when `CHANGELOG.md` or `Dockerfile` change — changelog-driven **git tag**, **GitHub Release**, **PyPI** (OIDC), and **GHCR** images when code paths in the push warrant a rebuild.
