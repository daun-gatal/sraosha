# Sraosha — Project Specification

> **For AI coding assistants:** This document is the single source of truth for the Sraosha project. Read it fully before generating any code. Follow the build order in Section 6 strictly. Each phase must be complete and tested before moving to the next.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Problem Statement](#2-problem-statement)
3. [Positioning & Differentiation](#3-positioning--differentiation)
4. [Architecture](#4-architecture)
5. [Tech Stack](#5-tech-stack)
6. [Build Order (Phases)](#6-build-order-phases)
7. [Project Structure](#7-project-structure)
8. [Module Specifications](#8-module-specifications)
   - [8.1 Core Engine](#81-core-engine)
   - [8.2 Pipeline Hooks](#82-pipeline-hooks)
   - [8.3 Drift Guard](#83-drift-guard)
   - [8.4 Impact Map](#84-impact-map)
   - [8.5 Compliance Dashboard (API)](#85-compliance-dashboard-api)
   - [8.6 Frontend Dashboard](#86-frontend-dashboard)
   - [8.7 CLI Interface](#87-cli-interface)
   - [8.8 Alerting](#88-alerting)
9. [Database Schema](#9-database-schema)
10. [Configuration Schema](#10-configuration-schema)
11. [Data Contract Format](#11-data-contract-format)
12. [API Reference](#12-api-reference)
13. [Environment Variables](#13-environment-variables)
14. [Testing Strategy](#14-testing-strategy)
15. [Docker & Deployment](#15-docker--deployment)
16. [README Template](#16-readme-template)

---

## 1. Project Overview

**Name:** Sraosha  
**Tagline:** The enforcement and governance runtime for data contracts.  
**Type:** Open-source Python project (MIT license)  
**Language:** Python (backend), TypeScript/React (frontend)  
**Target users:** Data Engineers, Data Platform teams, Analytics Engineers

Sraosha is **not** a replacement for `datacontract-cli`. It is a governance runtime that wraps `datacontract-cli` as its validation engine and adds what the CLI cannot do on its own:

- Blocking pipelines at runtime when contracts are violated
- Detecting statistical drift *before* a threshold is breached
- Mapping cross-contract impact when a schema change is proposed
- Tracking compliance history over time with team-level scoring
- Providing a self-hosted web dashboard for all of the above

---

## 2. Problem Statement

### What `datacontract-cli` already solves
- Defining contracts in YAML (ODCS format)
- Running schema and quality tests on-demand
- Exporting contracts to various formats (dbt, SQL, Avro, etc.)
- Linting and validating contract YAML files

### What it does NOT solve (Sraosha's territory)

| Gap | Impact |
|---|---|
| No native pipeline integration | Engineers must manually trigger tests; pipelines don't block on violations |
| No drift detection | Violations are found after breach, not before |
| No cross-contract awareness | Changing one contract has unknown downstream effects |
| No compliance history | No way to track SLA trends or team reliability over time |
| No centralized governance UI | No single pane of glass for contract health across the org |
| No real-time alerting | Engineers find out about violations from angry stakeholders |

---

## 3. Positioning & Differentiation

### vs. `datacontract-cli`
Sraosha **uses** `datacontract-cli` as a dependency. It calls the CLI's Python SDK internally. This makes it complementary, not competitive.

### vs. Monte Carlo / Bigeye
Those are expensive, cloud-only SaaS tools. Sraosha is fully self-hosted, open-source, and contract-first (not anomaly-detection-first).

### vs. Great Expectations / Soda
Those are quality frameworks. Sraosha is a **governance platform** — it enforces agreements between producers and consumers, not just quality rules.

### Positioning Statement
> "Sraosha is to data contracts what GitHub Actions is to code — the enforcement and observability runtime, not the authoring tool."

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Existing Data Stack                          │
│   Airflow / Prefect    dbt    Kafka    Spark    GitHub Actions  │
└───────┬──────────────────┬──────────────────────────────────────┘
        │ hooks/operators  │ hooks
        ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Sraosha Runtime                           │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌─────────────┐  │
│  │  Enforcer  │ │ DriftGuard │ │ ImpactMap  │ │ Compliance  │  │
│  │            │ │            │ │            │ │ Tracker     │  │
│  │ Blocks     │ │ Detects    │ │ Cross-     │ │ SLA history │  │
│  │ pipelines  │ │ trends     │ │ contract   │ │ team scores │  │
│  │ on breach  │ │ pre-breach │ │ dep graph  │ │ dashboards  │  │
│  └────────────┘ └────────────┘ └────────────┘ └─────────────┘  │
│                         ▲                                       │
│                  Core Engine (Python SDK)                       │
└───────────────────────────────┬─────────────────────────────────┘
                                │ wraps
                                ▼
                   ┌──────────────────────┐
                   │   datacontract-cli   │
                   │   (validation eng.)  │
                   └──────────────────────┘
```

### Data Flow

```
1. Pipeline starts (Airflow DAG, dbt run, etc.)
2. Sraosha hook is triggered (pre-execution)
3. Core Engine loads contract for the target dataset
4. datacontract-cli validates schema + quality rules
5. DriftGuard checks statistical trend for the dataset
6. If enforcement_mode = "block" and any check fails → pipeline aborts
7. If enforcement_mode = "warn" → pipeline continues, alert sent
8. Results are persisted to PostgreSQL (run history)
9. Compliance Tracker updates SLA score for the data producer
10. Dashboard reflects new state in real time
```

---

## 5. Tech Stack

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Core language | Python | 3.11+ | Required |
| Contract validation | datacontract-cli | latest | Used as Python library |
| Database | PostgreSQL | 15+ | Run history, metrics, contracts |
| ORM | SQLAlchemy | 2.x | Async support |
| Migrations | Alembic | latest | Auto-generated migrations |
| In-process analytics | DuckDB | latest | Drift detection queries |
| API framework | FastAPI | latest | Async, auto OpenAPI docs |
| Task queue | Celery + Redis | latest | Background drift scans |
| Frontend | React + TypeScript | latest | Bun (runtime, package manager, bundler) |
| UI components | shadcn/ui + Tailwind | latest | Consistent design |
| Charts | Recharts | latest | Compliance trend charts |
| Airflow integration | Apache Airflow | 2.7+ | Custom provider package |
| dbt integration | dbt-core | 1.7+ | Hooks via on-run-end |
| CLI | Typer | latest | `sraosha` command |
| Containerization | Docker + Compose | latest | Full stack deployment |
| Testing | pytest + pytest-asyncio | latest | All unit and integration tests |
| Linting | ruff | latest | Fast Python linter |

---

## 6. Build Order (Phases)

> **IMPORTANT FOR AI ASSISTANTS:** Build phases in this exact order. Do not skip ahead. Each phase produces working, testable code before the next begins.

### Phase 1 — Project Scaffold & Core Engine
**Goal:** A working Python package that can load a contract and run validation using `datacontract-cli`.

Build in this order:
1. `pyproject.toml` with all dependencies
2. `sraosha/config.py` — Pydantic settings model
3. `sraosha/models/` — SQLAlchemy ORM models
4. `sraosha/db.py` — database engine and session factory
5. `alembic/` — migration setup
6. `sraosha/core/engine.py` — `ContractEngine` class
7. `sraosha/core/loader.py` — contract loader (from file, URL, Git)
8. `sraosha/core/runner.py` — validation runner (wraps datacontract-cli)
9. Unit tests for Phase 1
10. Verify: `python -m sraosha.core.runner --contract path/to/contract.yaml` runs successfully

### Phase 2 — Pipeline Hooks
**Goal:** Airflow operator and dbt hook that call the Core Engine and enforce contracts.

Build in this order:
1. `sraosha/hooks/base.py` — abstract `BasePipelineHook`
2. `sraosha/hooks/airflow/operator.py` — `SraoshaOperator`
3. `sraosha/hooks/airflow/provider.py` — Airflow provider descriptor
4. `sraosha/hooks/dbt/macro.py` — dbt on-run-end hook macro
5. `sraosha/hooks/dbt/hook.py` — Python dbt hook runner
6. Integration tests with a mock Airflow DAG
7. Verify: A sample Airflow DAG with `SraoshaOperator` blocks when contract fails

### Phase 3 — Drift Guard
**Goal:** A module that computes statistical metrics per table over time and raises pre-breach warnings.

Build in this order:
1. `sraosha/drift/metrics.py` — metric definitions (null rate, row count delta, type distribution)
2. `sraosha/drift/scanner.py` — `DriftScanner` class using DuckDB
3. `sraosha/drift/baseline.py` — baseline computation from historical runs
4. `sraosha/drift/alerter.py` — threshold comparison and alert dispatch
5. Celery task: `sraosha/tasks/drift_scan.py`
6. Unit tests with synthetic metric data
7. Verify: Scanner detects a rising null rate trend over 5 mock runs

### Phase 4 — REST API (FastAPI)
**Goal:** A complete REST API exposing all Sraosha functionality.

Build in this order:
1. `sraosha/api/app.py` — FastAPI app factory
2. `sraosha/api/deps.py` — dependency injection (db session, engine)
3. `sraosha/api/routers/contracts.py` — contract CRUD endpoints
4. `sraosha/api/routers/runs.py` — run history endpoints
5. `sraosha/api/routers/drift.py` — drift metrics endpoints
6. `sraosha/api/routers/compliance.py` — SLA and team score endpoints
7. `sraosha/api/routers/impact.py` — impact map endpoints
8. API integration tests (pytest + httpx)
9. Verify: All endpoints return correct data with OpenAPI docs at `/docs`

### Phase 5 — Impact Map
**Goal:** A module that builds a dependency graph across contracts and shows what breaks when a contract changes.

Build in this order:
1. `sraosha/impact/parser.py` — extract field-level references from contracts
2. `sraosha/impact/graph.py` — build NetworkX dependency graph
3. `sraosha/impact/analyzer.py` — impact analysis for a proposed change
4. `sraosha/api/routers/impact.py` — expose graph as API
5. Verify: Changing a field in Contract A correctly identifies affected Contract B and C

### Phase 6 — Frontend Dashboard
**Goal:** React dashboard showing contract health, run history, drift trends, and compliance scores.

Build in this order:
1. Bun + React + TypeScript project scaffold in `dashboard/` (`bun create react-app` or manual setup with `bun init`)
2. `dashboard/src/api/client.ts` — typed API client for FastAPI
3. `dashboard/src/pages/Overview.tsx` — contract health summary
4. `dashboard/src/pages/ContractDetail.tsx` — single contract view with run history
5. `dashboard/src/pages/DriftMetrics.tsx` — trend charts per table
6. `dashboard/src/pages/Compliance.tsx` — team scores and SLA history
7. `dashboard/src/pages/ImpactMap.tsx` — interactive dependency graph
8. Verify: Dashboard loads and displays data from local API

### Phase 7 — CLI, Alerting & Packaging
**Goal:** Polish the `sraosha` CLI, add Slack/email alerting, and prepare for open-source release.

Build in this order:
1. `sraosha/cli/main.py` — Typer CLI with all commands
2. `sraosha/alerting/slack.py` — Slack webhook notifier
3. `sraosha/alerting/email.py` — SMTP email notifier
4. `sraosha/alerting/dispatcher.py` — route alerts to configured channels
5. `docker-compose.yml` — full stack (API + DB + Redis + Celery + Dashboard)
6. `Dockerfile` for API
7. `Dockerfile` for Dashboard
8. `README.md` — complete documentation
9. Verify: `docker compose up` starts full stack; `sraosha run` works from CLI

---

## 7. Project Structure

```
sraosha/
├── sraosha/                        # Main Python package
│   ├── __init__.py
│   ├── config.py                    # Pydantic settings (from env vars)
│   ├── db.py                        # SQLAlchemy engine, session factory
│   │
│   ├── models/                      # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── contract.py              # Contract model
│   │   ├── run.py                   # ValidationRun model
│   │   ├── metric.py                # DriftMetric model
│   │   ├── alert.py                 # Alert model
│   │   └── team.py                  # Team and compliance score models
│   │
│   ├── schemas/                     # Pydantic request/response schemas
│   │   ├── __init__.py
│   │   ├── contract.py
│   │   ├── run.py
│   │   ├── drift.py
│   │   ├── compliance.py
│   │   └── impact.py
│   │
│   ├── core/                        # Core validation engine
│   │   ├── __init__.py
│   │   ├── engine.py                # ContractEngine main class
│   │   ├── loader.py                # Load contracts from file/URL/git
│   │   └── runner.py                # Wraps datacontract-cli SDK
│   │
│   ├── drift/                       # Drift detection module
│   │   ├── __init__.py
│   │   ├── metrics.py               # Metric definitions and computation
│   │   ├── scanner.py               # DriftScanner class (uses DuckDB)
│   │   ├── baseline.py              # Baseline computation
│   │   └── alerter.py               # Threshold comparison + alert dispatch
│   │
│   ├── impact/                      # Impact map module
│   │   ├── __init__.py
│   │   ├── parser.py                # Parse field-level references from contracts
│   │   ├── graph.py                 # Build NetworkX dependency graph
│   │   └── analyzer.py              # Impact analysis for proposed changes
│   │
│   ├── hooks/                       # Pipeline integration hooks
│   │   ├── __init__.py
│   │   ├── base.py                  # Abstract BasePipelineHook
│   │   ├── airflow/
│   │   │   ├── __init__.py
│   │   │   ├── operator.py          # SraoshaOperator
│   │   │   └── provider.py          # Airflow provider descriptor
│   │   └── dbt/
│   │       ├── __init__.py
│   │       ├── hook.py              # Python dbt hook runner
│   │       └── macros/
│   │           └── sraosha_check.sql  # dbt macro for on-run-end
│   │
│   ├── alerting/                    # Alerting module
│   │   ├── __init__.py
│   │   ├── base.py                  # Abstract BaseAlerter
│   │   ├── slack.py                 # Slack webhook notifier
│   │   ├── email.py                 # SMTP email notifier
│   │   └── dispatcher.py           # Route alerts to configured channels
│   │
│   ├── tasks/                       # Celery background tasks
│   │   ├── __init__.py
│   │   ├── celery_app.py            # Celery app factory
│   │   ├── drift_scan.py            # Periodic drift scan task
│   │   └── compliance_compute.py   # Periodic compliance score recompute
│   │
│   ├── api/                         # FastAPI application
│   │   ├── __init__.py
│   │   ├── app.py                   # FastAPI app factory
│   │   ├── deps.py                  # Dependency injection
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── contracts.py         # /contracts endpoints
│   │       ├── runs.py              # /runs endpoints
│   │       ├── drift.py             # /drift endpoints
│   │       ├── compliance.py        # /compliance endpoints
│   │       └── impact.py            # /impact endpoints
│   │
│   └── cli/                         # Typer CLI
│       ├── __init__.py
│       └── main.py                  # sraosha CLI commands
│
├── dashboard/                       # React TypeScript frontend
│   ├── package.json
│   ├── bunfig.toml
│   ├── tsconfig.json
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/
│       │   └── client.ts            # Typed API client
│       ├── components/
│       │   ├── ContractHealthBadge.tsx
│       │   ├── RunHistoryTable.tsx
│       │   ├── DriftChart.tsx
│       │   ├── ImpactGraph.tsx
│       │   └── ComplianceScore.tsx
│       └── pages/
│           ├── Overview.tsx
│           ├── ContractDetail.tsx
│           ├── DriftMetrics.tsx
│           ├── Compliance.tsx
│           └── ImpactMap.tsx
│
├── alembic/                         # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── tests/                           # All tests
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_engine.py
│   │   ├── test_runner.py
│   │   ├── test_drift.py
│   │   ├── test_impact.py
│   │   └── test_alerting.py
│   ├── integration/
│   │   ├── test_api.py
│   │   ├── test_airflow_operator.py
│   │   └── test_dbt_hook.py
│   └── fixtures/
│       ├── sample_contract.yaml
│       └── sample_contract_broken.yaml
│
├── examples/                        # Usage examples
│   ├── airflow_dag_example.py
│   ├── dbt_project_example/
│   └── standalone_example.py
│
├── docker-compose.yml
├── Dockerfile
├── Dockerfile.dashboard
├── pyproject.toml
├── alembic.ini
├── .env.example
└── README.md
```

---

## 8. Module Specifications

### 8.1 Core Engine

**File:** `sraosha/core/engine.py`

The `ContractEngine` is the central class that all other modules interact with.

```python
# sraosha/core/engine.py

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

class EnforcementMode(str, Enum):
    BLOCK = "block"   # Raise exception on violation
    WARN  = "warn"    # Log warning, continue
    LOG   = "log"     # Silently log, continue

@dataclass
class ValidationResult:
    contract_id: str
    contract_path: str
    passed: bool
    enforcement_mode: EnforcementMode
    checks_total: int
    checks_passed: int
    checks_failed: int
    failures: list[dict]       # List of {check, field, message}
    duration_seconds: float
    run_id: str                # UUID for this run
    timestamp: str             # ISO 8601

class ContractEngine:
    """
    Main entry point for Sraosha.
    Loads a contract, runs validation via datacontract-cli, persists results.
    """
    def __init__(
        self,
        contract_path: str | Path,
        enforcement_mode: EnforcementMode = EnforcementMode.BLOCK,
        server: Optional[str] = None,         # Which server block to test against
        db_session = None,                    # SQLAlchemy session for persistence
        dry_run: bool = False,                # If True, run but don't persist or alert
    ):
        ...

    def run(self) -> ValidationResult:
        """
        Execute the full validation cycle:
        1. Load the contract
        2. Run datacontract-cli validation
        3. Persist results to DB
        4. Dispatch alerts if needed
        5. Raise ContractViolationError if BLOCK mode and failed
        """
        ...

    def check_drift(self) -> "DriftResult":
        """
        After a successful run, check if metrics are trending toward violation.
        """
        ...

class ContractViolationError(Exception):
    """Raised when enforcement_mode=BLOCK and contract validation fails."""
    def __init__(self, result: ValidationResult):
        self.result = result
        super().__init__(
            f"Contract '{result.contract_id}' failed: "
            f"{result.checks_failed}/{result.checks_total} checks failed."
        )
```

---

**File:** `sraosha/core/loader.py`

```python
# sraosha/core/loader.py

class ContractLoader:
    """
    Loads a datacontract.yaml from various sources.
    Supported: local file path, HTTP/HTTPS URL, Git repo URL (auto-clones)
    """

    @staticmethod
    def from_file(path: str | Path) -> dict:
        """Load and parse a local YAML contract file."""
        ...

    @staticmethod
    def from_url(url: str) -> dict:
        """Fetch and parse a contract from an HTTP/HTTPS URL."""
        ...

    @staticmethod
    def from_git(repo_url: str, file_path: str, branch: str = "main") -> dict:
        """
        Clone a git repo (shallow) and load a contract file from it.
        Uses a temp directory, cleaned up after loading.
        """
        ...

    @staticmethod
    def auto(source: str) -> dict:
        """
        Auto-detect source type and delegate to the correct loader.
        Detects: local path, http://, https://, git+https://
        """
        ...
```

---

**File:** `sraosha/core/runner.py`

```python
# sraosha/core/runner.py
# Wraps the datacontract-cli Python SDK

from datacontract.data_contract import DataContract

class ContractRunner:
    """
    Wraps datacontract-cli's DataContract class.
    Normalizes its output into Sraosha's ValidationResult format.
    """

    def __init__(self, contract_path: str, server: str | None = None):
        self.contract_path = contract_path
        self.server = server
        self._dc = DataContract(data_contract_file=contract_path)

    def run(self) -> dict:
        """
        Execute datacontract-cli tests.
        Returns a normalized dict ready to be converted to ValidationResult.
        Schema:
        {
            "passed": bool,
            "checks_total": int,
            "checks_passed": int,
            "checks_failed": int,
            "failures": [{"check": str, "field": str, "message": str}],
            "duration_seconds": float
        }
        """
        ...
```

---

### 8.2 Pipeline Hooks

**File:** `sraosha/hooks/base.py`

```python
# sraosha/hooks/base.py

from abc import ABC, abstractmethod
from sraosha.core.engine import ContractEngine, EnforcementMode, ValidationResult

class BasePipelineHook(ABC):
    """
    Abstract base for all pipeline integration hooks.
    Subclass this for Airflow, dbt, Prefect, etc.
    """

    def __init__(
        self,
        contract_path: str,
        enforcement_mode: EnforcementMode = EnforcementMode.BLOCK,
        server: str | None = None,
    ):
        self.contract_path = contract_path
        self.enforcement_mode = enforcement_mode
        self.server = server

    def execute(self) -> ValidationResult:
        """Run the engine and return the result. Raises on BLOCK mode failure."""
        engine = ContractEngine(
            contract_path=self.contract_path,
            enforcement_mode=self.enforcement_mode,
            server=self.server,
        )
        return engine.run()

    @abstractmethod
    def on_success(self, result: ValidationResult) -> None:
        """Called after a passing validation."""
        ...

    @abstractmethod
    def on_failure(self, result: ValidationResult) -> None:
        """Called after a failing validation (before raising)."""
        ...
```

---

**File:** `sraosha/hooks/airflow/operator.py`

```python
# sraosha/hooks/airflow/operator.py

from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults
from sraosha.core.engine import ContractEngine, EnforcementMode

class SraoshaOperator(BaseOperator):
    """
    Airflow operator that validates a data contract before or after a task.

    Usage in DAG:
        validate_orders = SraoshaOperator(
            task_id="validate_orders_contract",
            contract_path="contracts/orders.yaml",
            enforcement_mode="block",
            server="production",
            dag=dag,
        )
        load_orders >> validate_orders >> transform_orders

    Parameters:
        contract_path (str): Path or URL to the datacontract.yaml file.
        enforcement_mode (str): "block" | "warn" | "log". Default: "block".
        server (str): Which server block to test against. Default: None (all).
        sraosha_api_url (str): Optional Sraosha API URL to push results.
    """

    template_fields = ("contract_path", "server")
    ui_color = "#6366f1"

    @apply_defaults
    def __init__(
        self,
        contract_path: str,
        enforcement_mode: str = "block",
        server: str | None = None,
        sraosha_api_url: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.contract_path = contract_path
        self.enforcement_mode = EnforcementMode(enforcement_mode)
        self.server = server
        self.sraosha_api_url = sraosha_api_url

    def execute(self, context: dict):
        """
        Called by Airflow when the task runs.
        Runs contract validation and handles enforcement.
        Pushes results to Sraosha API if sraosha_api_url is set.
        """
        ...
```

---

**File:** `sraosha/hooks/dbt/hook.py`

```python
# sraosha/hooks/dbt/hook.py
# Called via dbt's on-run-end hook in dbt_project.yml:
#   on-run-end:
#     - "{{ sraosha_check(contract_path='contracts/orders.yaml') }}"
# Or directly as a Python runner:
#   python -m sraosha.hooks.dbt.hook --contract contracts/orders.yaml

class DbtHook:
    """
    Runs Sraosha validation as part of a dbt run lifecycle.
    Can be invoked:
      1. From a dbt macro (compiles to a shell call)
      2. Directly from Python after dbt run completes
    """

    def __init__(self, contract_path: str, enforcement_mode: str = "block"):
        ...

    def run(self) -> None:
        """Execute validation. Exits with code 1 if BLOCK mode and failed."""
        ...
```

---

### 8.3 Drift Guard

**File:** `sraosha/drift/metrics.py`

```python
# sraosha/drift/metrics.py

from dataclasses import dataclass
from enum import Enum

class MetricType(str, Enum):
    NULL_RATE        = "null_rate"         # % of null values per column
    ROW_COUNT        = "row_count"         # total rows in table
    ROW_COUNT_DELTA  = "row_count_delta"   # % change from previous run
    TYPE_MISMATCH    = "type_mismatch"     # % of rows failing type check
    DUPLICATE_RATE   = "duplicate_rate"    # % of duplicate rows on PK
    VALUE_DIST       = "value_dist"        # Distribution shift (KL divergence)

@dataclass
class MetricDefinition:
    """Defines a single metric to track for a contract field."""
    metric_type: MetricType
    table: str
    column: str | None     # None for table-level metrics (row_count)
    warning_threshold: float   # Alert when metric exceeds this
    breach_threshold: float    # Contract violation threshold (from contract)

@dataclass
class MetricValue:
    """A single measured metric at a point in time."""
    metric_type: MetricType
    table: str
    column: str | None
    value: float
    run_id: str
    measured_at: str           # ISO 8601
```

---

**File:** `sraosha/drift/scanner.py`

```python
# sraosha/drift/scanner.py

import duckdb
from sraosha.drift.metrics import MetricDefinition, MetricValue, MetricType

class DriftScanner:
    """
    Computes statistical metrics for a dataset using DuckDB.
    Works with any source DuckDB can read: Parquet, CSV, Delta, Postgres (via ATTACH).

    Usage:
        scanner = DriftScanner(source="s3://bucket/orders/*.parquet")
        values = scanner.compute([
            MetricDefinition(MetricType.NULL_RATE, "orders", "customer_id", 0.02, 0.05),
            MetricDefinition(MetricType.ROW_COUNT,  "orders", None,          None, None),
        ])
    """

    def __init__(self, source: str, source_type: str = "parquet"):
        """
        source: DuckDB-readable path or connection string
        source_type: "parquet" | "csv" | "delta" | "postgres" | "bigquery"
        """
        self.source = source
        self.source_type = source_type
        self.conn = duckdb.connect()

    def compute(self, metrics: list[MetricDefinition]) -> list[MetricValue]:
        """Compute all requested metrics and return measured values."""
        ...

    def _compute_null_rate(self, table: str, column: str) -> float:
        """SELECT COUNT(*) FILTER (WHERE col IS NULL) / COUNT(*) FROM table"""
        ...

    def _compute_row_count(self, table: str) -> float:
        """SELECT COUNT(*) FROM table"""
        ...

    def _compute_row_count_delta(self, table: str, previous_count: float) -> float:
        """(current - previous) / previous"""
        ...
```

---

**File:** `sraosha/drift/baseline.py`

```python
# sraosha/drift/baseline.py

class BaselineComputer:
    """
    Computes statistical baselines from the last N runs of a contract.
    Used to determine if a new metric value is anomalous.

    Baseline per metric = {mean, std_dev, p25, p75, p95, trend_slope}
    trend_slope is computed via linear regression on the last N values.
    A positive slope for null_rate means nulls are increasing — pre-breach warning.
    """

    def __init__(self, db_session, window_size: int = 14):
        """window_size: number of past runs to use for baseline computation"""
        self.session = db_session
        self.window_size = window_size

    def compute_for_contract(self, contract_id: str) -> dict[str, dict]:
        """
        Returns a dict keyed by "{table}.{column}.{metric_type}" with baseline stats.
        {
            "orders.customer_id.null_rate": {
                "mean": 0.012,
                "std_dev": 0.003,
                "trend_slope": 0.0008,   # positive = getting worse
                "is_trending_to_breach": True,
                "estimated_breach_in_runs": 6
            }
        }
        """
        ...
```

---

### 8.4 Impact Map

**File:** `sraosha/impact/graph.py`

```python
# sraosha/impact/graph.py

import networkx as nx

class ContractDependencyGraph:
    """
    Builds a directed graph of cross-contract dependencies.

    Nodes: contracts (keyed by contract_id)
    Edges: contract A → contract B if B references fields from A
           (detected by: same table name referenced in server block + field overlap)

    The graph is rebuilt whenever contracts are updated.
    """

    def __init__(self):
        self.graph = nx.DiGraph()

    def add_contract(self, contract: dict) -> None:
        """Parse a contract dict and add it as a node with its field metadata."""
        ...

    def build_edges(self) -> None:
        """
        After all contracts are added, detect dependencies:
        1. If Contract B's server block points to a table that Contract A owns
        2. And Contract B references fields that exist in Contract A
        → Add edge A → B (A produces data that B consumes)
        """
        ...

    def get_downstream(self, contract_id: str, depth: int = -1) -> list[str]:
        """Return all contract IDs downstream of the given contract."""
        ...

    def get_impact_of_change(self, contract_id: str, changed_fields: list[str]) -> dict:
        """
        Given a proposed field change in contract_id, return:
        {
            "directly_affected": [contract_id, ...],
            "transitively_affected": [contract_id, ...],
            "severity": "high" | "medium" | "low",
            "affected_pipelines": [pipeline_id, ...]
        }
        """
        ...

    def to_json(self) -> dict:
        """Serialize graph to JSON for the frontend (nodes + edges format)."""
        ...
```

---

### 8.5 Compliance Dashboard (API)

**File:** `sraosha/api/app.py`

```python
# sraosha/api/app.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sraosha.api.routers import contracts, runs, drift, compliance, impact

def create_app() -> FastAPI:
    app = FastAPI(
        title="Sraosha API",
        description="Governance runtime for data contracts",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],     # Restrict in production
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(contracts.router, prefix="/api/v1/contracts", tags=["Contracts"])
    app.include_router(runs.router,      prefix="/api/v1/runs",      tags=["Runs"])
    app.include_router(drift.router,     prefix="/api/v1/drift",     tags=["Drift"])
    app.include_router(compliance.router,prefix="/api/v1/compliance",tags=["Compliance"])
    app.include_router(impact.router,    prefix="/api/v1/impact",    tags=["Impact"])

    return app
```

---

**File:** `sraosha/api/routers/contracts.py`

```python
# All endpoints must be fully typed with Pydantic response models.

# GET    /api/v1/contracts                    → list all contracts
# POST   /api/v1/contracts                    → register a new contract
# GET    /api/v1/contracts/{contract_id}      → get single contract details
# PUT    /api/v1/contracts/{contract_id}      → update contract
# DELETE /api/v1/contracts/{contract_id}      → remove contract
# POST   /api/v1/contracts/{contract_id}/run  → trigger an immediate validation run
```

**File:** `sraosha/api/routers/runs.py`

```python
# GET /api/v1/runs                                          → list all runs (paginated)
# GET /api/v1/runs/{run_id}                                 → single run detail with failures
# GET /api/v1/runs?contract_id={id}&limit=20&offset=0       → runs for a specific contract
# GET /api/v1/runs/summary                                  → aggregated pass/fail counts per contract
```

**File:** `sraosha/api/routers/drift.py`

```python
# GET /api/v1/drift/{contract_id}                       → current drift status per metric
# GET /api/v1/drift/{contract_id}/history               → time-series metric values
# GET /api/v1/drift/{contract_id}/baseline              → computed baseline per metric
# GET /api/v1/drift/alerts                              → all active pre-breach warnings
```

**File:** `sraosha/api/routers/compliance.py`

```python
# GET /api/v1/compliance/teams                          → all teams with SLA scores
# GET /api/v1/compliance/teams/{team_id}                → single team detail + trend
# GET /api/v1/compliance/contracts/{contract_id}/sla    → SLA history for a contract
# GET /api/v1/compliance/leaderboard                   → ranked teams by compliance score
```

**File:** `sraosha/api/routers/impact.py`

```python
# GET /api/v1/impact/graph                              → full contract dependency graph (JSON)
# GET /api/v1/impact/{contract_id}/downstream          → downstream contracts
# POST /api/v1/impact/{contract_id}/analyze            → analyze impact of proposed field changes
#   body: { "changed_fields": ["field_a", "field_b"] }
```

---

### 8.6 Frontend Dashboard

**Pages and their data requirements:**

#### Overview (`/`)
- Summary cards: Total contracts, passing %, active drift alerts, recent violations
- Contract health table: contract_id | owner_team | status | last_run | trend
- Color coding: green (passing), amber (drift warning), red (failing)

#### Contract Detail (`/contracts/:id`)
- Contract metadata panel (from YAML: title, description, server, owner)
- Run history table: timestamp | duration | checks_passed | checks_failed | status
- Expandable failure details per run
- Drift metric charts (Recharts LineChart, last 30 runs)
- Link to Impact Map for this contract

#### Drift Metrics (`/drift`)
- Filterable by contract, table, column, metric type
- LineChart per metric showing trend + warning threshold line + breach threshold line
- Badge: "Trending to breach in ~N runs" if trend_slope is concerning

#### Compliance (`/compliance`)
- Team leaderboard table: rank | team | score | contracts_owned | violations_30d
- Score formula (display it): `score = (runs_passed / total_runs) * 100` over last 30 days
- SLA history chart per team

#### Impact Map (`/impact`)
- Interactive force-directed graph using `react-force-graph` or `d3`
- Node = contract (colored by health status)
- Edge = dependency direction
- Click node → highlight upstream and downstream
- Side panel: proposed change analyzer (input fields → show affected contracts)

---

### 8.7 CLI Interface

**File:** `sraosha/cli/main.py`

All commands use `typer`. The CLI is installed as the `sraosha` command.

```bash
# Run validation for a contract
sraosha run --contract path/to/contract.yaml [--mode block|warn|log] [--server production]

# Show status of all registered contracts
sraosha status [--format table|json]

# Show run history for a contract
sraosha history --contract <contract_id> [--limit 20]

# Show current drift status
sraosha drift --contract <contract_id>

# Register a contract with the Sraosha API
sraosha register --contract path/to/contract.yaml --team my-team

# Show impact of a proposed change
sraosha impact --contract <contract_id> --fields field_a,field_b

# Start the API server (development)
sraosha serve [--host 0.0.0.0] [--port 8000] [--reload]

# Run database migrations
sraosha db upgrade

# Show version
sraosha version
```

---

### 8.8 Alerting

**File:** `sraosha/alerting/dispatcher.py`

```python
# sraosha/alerting/dispatcher.py

class AlertDispatcher:
    """
    Routes alerts to all configured channels.
    Configured via environment variables or sraosha config file.

    Supported channels: Slack, Email (SMTP)
    Alert types:
      - CONTRACT_VIOLATION: contract failed validation (with enforcement_mode=warn/log)
      - DRIFT_WARNING: metric trending toward breach
      - CONTRACT_BREACH: metric crossed breach threshold
    """

    def dispatch(self, alert_type: str, contract_id: str, details: dict) -> None:
        """Send alert to all enabled channels."""
        ...
```

**Slack alert payload format:**
```json
{
  "text": "⚠️ Sraosha: Drift Warning",
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Contract:* `orders_v1`\n*Metric:* `null_rate` on `customer_id`\n*Current:* 3.2% (warning at 2%)\n*Trend:* Breaching in ~4 runs"
      }
    }
  ]
}
```

---

## 9. Database Schema

All tables use PostgreSQL. Use SQLAlchemy 2.x mapped classes with Alembic migrations.

```sql
-- Registered data contracts
CREATE TABLE contracts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id     TEXT UNIQUE NOT NULL,   -- from YAML: id field
    title           TEXT NOT NULL,
    description     TEXT,
    file_path       TEXT NOT NULL,          -- local path or URL
    owner_team      TEXT,
    raw_yaml        TEXT NOT NULL,          -- full YAML content stored
    enforcement_mode TEXT NOT NULL DEFAULT 'block',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Individual validation run results
CREATE TABLE validation_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id     TEXT NOT NULL REFERENCES contracts(contract_id),
    status          TEXT NOT NULL,          -- 'passed' | 'failed' | 'error'
    enforcement_mode TEXT NOT NULL,
    checks_total    INT NOT NULL DEFAULT 0,
    checks_passed   INT NOT NULL DEFAULT 0,
    checks_failed   INT NOT NULL DEFAULT 0,
    failures        JSONB,                  -- [{check, field, message}]
    server          TEXT,
    triggered_by    TEXT,                   -- 'airflow' | 'dbt' | 'cli' | 'api' | 'schedule'
    duration_ms     INT,
    error_message   TEXT,                   -- if status = 'error'
    run_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Drift metric values per run
CREATE TABLE drift_metrics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id     TEXT NOT NULL REFERENCES contracts(contract_id),
    run_id          UUID REFERENCES validation_runs(id),
    metric_type     TEXT NOT NULL,          -- MetricType enum values
    table_name      TEXT NOT NULL,
    column_name     TEXT,                   -- NULL for table-level metrics
    value           DOUBLE PRECISION NOT NULL,
    warning_threshold DOUBLE PRECISION,
    breach_threshold  DOUBLE PRECISION,
    is_warning      BOOLEAN NOT NULL DEFAULT FALSE,
    is_breached     BOOLEAN NOT NULL DEFAULT FALSE,
    measured_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Computed drift baselines (refreshed by Celery task)
CREATE TABLE drift_baselines (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id     TEXT NOT NULL REFERENCES contracts(contract_id),
    metric_type     TEXT NOT NULL,
    table_name      TEXT NOT NULL,
    column_name     TEXT,
    mean            DOUBLE PRECISION,
    std_dev         DOUBLE PRECISION,
    trend_slope     DOUBLE PRECISION,       -- positive = worsening
    is_trending_to_breach BOOLEAN NOT NULL DEFAULT FALSE,
    estimated_breach_in_runs INT,
    window_size     INT NOT NULL,           -- number of runs used
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (contract_id, metric_type, table_name, column_name)
);

-- Dispatched alerts
CREATE TABLE alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id     TEXT NOT NULL REFERENCES contracts(contract_id),
    alert_type      TEXT NOT NULL,          -- 'contract_violation' | 'drift_warning' | 'breach'
    channel         TEXT NOT NULL,          -- 'slack' | 'email'
    payload         JSONB NOT NULL,
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    success         BOOLEAN NOT NULL DEFAULT TRUE,
    error_message   TEXT
);

-- Teams (for compliance tracking)
CREATE TABLE teams (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT UNIQUE NOT NULL,
    slack_channel   TEXT,
    email           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Compliance scores (computed by Celery, refreshed daily)
CREATE TABLE compliance_scores (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id         UUID NOT NULL REFERENCES teams(id),
    score           DOUBLE PRECISION NOT NULL,     -- 0.0 to 100.0
    total_runs      INT NOT NULL,
    passed_runs     INT NOT NULL,
    violations_count INT NOT NULL,
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (team_id, period_start, period_end)
);
```

---

## 10. Configuration Schema

**File:** `sraosha/config.py`

All configuration is loaded from environment variables (12-factor app style). Pydantic Settings is used for validation.

```python
from pydantic_settings import BaseSettings

class SraoshaSettings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://sraosha:sraosha@localhost:5432/sraosha"

    # Redis (for Celery)
    REDIS_URL: str = "redis://localhost:6379/0"

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_KEY: str | None = None              # If set, all API calls require X-API-Key header

    # Contracts
    CONTRACTS_DIR: str = "./contracts"      # Default directory to scan for contracts
    DEFAULT_ENFORCEMENT_MODE: str = "block"

    # Drift detection
    DRIFT_SCAN_INTERVAL_SECONDS: int = 3600  # How often to run background drift scans
    DRIFT_BASELINE_WINDOW: int = 14          # Past N runs to use for baseline

    # Alerting — Slack
    SLACK_WEBHOOK_URL: str | None = None
    SLACK_ENABLED: bool = False

    # Alerting — Email
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str | None = None
    EMAIL_ENABLED: bool = False

    # Frontend
    DASHBOARD_URL: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        case_sensitive = True
```

---

## 11. Data Contract Format

Sraosha uses the **Open Data Contract Standard (ODCS)** format, which is what `datacontract-cli` natively supports. Contracts are YAML files.

Sraosha adds an optional `x-sraosha` extension block for additional governance metadata:

```yaml
# orders.yaml — example contract with Sraosha extension

dataContractSpecification: 1.1.0
id: orders-v1
info:
  title: Orders
  version: 1.0.0
  description: Order data produced by the checkout service
  owner: team-checkout
  contact:
    name: Checkout Team
    email: checkout@company.com

servers:
  production:
    type: postgres
    host: db.company.com
    port: 5432
    database: warehouse
    schema: orders

models:
  orders:
    type: table
    fields:
      order_id:
        type: uuid
        required: true
        unique: true
      customer_id:
        type: text
        required: true
      order_total:
        type: integer
        required: true
      order_timestamp:
        type: timestamptz
        required: true

quality:
  - type: sql
    query: "SELECT COUNT(*) FROM orders WHERE order_total < 0"
    mustBe: 0

serviceLevel:
  freshness:
    description: "Data must be updated within 1 hour"
    threshold: 1h
  availability:
    description: "Table must be accessible"
    percentage: 99.9

# Sraosha extension — optional
x-sraosha:
  owner_team: team-checkout
  enforcement_mode: block          # block | warn | log
  drift_metrics:
    - table: orders
      column: customer_id
      metric: null_rate
      warning_threshold: 0.02      # alert at 2%
      breach_threshold: 0.05       # contract says max 5%
    - table: orders
      column: null                 # table-level metric
      metric: row_count_delta
      warning_threshold: 0.20     # alert if row count changes >20%
      breach_threshold: 0.50
  notify:
    slack_channel: "#data-contracts"
    email: "checkout-team@company.com"
```

---

## 12. API Reference

### Contracts

| Method | Endpoint | Description | Request Body | Response |
|---|---|---|---|---|
| GET | `/api/v1/contracts` | List all contracts | — | `ContractListResponse` |
| POST | `/api/v1/contracts` | Register contract | `ContractCreateRequest` | `ContractResponse` |
| GET | `/api/v1/contracts/{id}` | Get contract detail | — | `ContractDetailResponse` |
| PUT | `/api/v1/contracts/{id}` | Update contract | `ContractUpdateRequest` | `ContractResponse` |
| DELETE | `/api/v1/contracts/{id}` | Remove contract | — | `204 No Content` |
| POST | `/api/v1/contracts/{id}/run` | Trigger validation | `RunRequest` | `ValidationRunResponse` |

### Runs

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/runs` | List all runs (paginated, filterable by contract_id) |
| GET | `/api/v1/runs/{run_id}` | Single run detail with full failure list |
| GET | `/api/v1/runs/summary` | Pass/fail counts per contract (for dashboard overview) |

### Drift

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/drift/{contract_id}` | Current drift status (latest values per metric) |
| GET | `/api/v1/drift/{contract_id}/history` | Time-series metric values (last N runs) |
| GET | `/api/v1/drift/{contract_id}/baseline` | Computed baseline stats per metric |
| GET | `/api/v1/drift/alerts` | All active pre-breach warnings across all contracts |

### Compliance

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/compliance/teams` | All teams with current SLA scores |
| GET | `/api/v1/compliance/teams/{team_id}` | Team detail + 30-day score trend |
| GET | `/api/v1/compliance/contracts/{id}/sla` | SLA history for a specific contract |
| GET | `/api/v1/compliance/leaderboard` | Teams ranked by compliance score |

### Impact

| Method | Endpoint | Description | Request Body |
|---|---|---|---|
| GET | `/api/v1/impact/graph` | Full dependency graph (nodes + edges JSON) | — |
| GET | `/api/v1/impact/{id}/downstream` | All downstream contracts | — |
| POST | `/api/v1/impact/{id}/analyze` | Analyze impact of proposed field changes | `{ "changed_fields": ["field_a"] }` |

---

## 13. Environment Variables

```bash
# .env.example

# === Database ===
DATABASE_URL=postgresql+asyncpg://sraosha:sraosha@localhost:5432/sraosha

# === Redis (Celery) ===
REDIS_URL=redis://localhost:6379/0

# === API ===
API_HOST=0.0.0.0
API_PORT=8000
API_KEY=                          # Leave empty to disable auth (dev only)

# === Contracts ===
CONTRACTS_DIR=./contracts
DEFAULT_ENFORCEMENT_MODE=block

# === Drift Detection ===
DRIFT_SCAN_INTERVAL_SECONDS=3600
DRIFT_BASELINE_WINDOW=14

# === Slack Alerting ===
SLACK_ENABLED=false
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ

# === Email Alerting ===
EMAIL_ENABLED=false
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your@email.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=sraosha@yourcompany.com

# === Dashboard ===
DASHBOARD_URL=http://localhost:5173
```

---

## 14. Testing Strategy

### Unit Tests
Every module has a corresponding unit test file. Use `pytest`. Mock `datacontract-cli` calls with `unittest.mock`. Use in-memory SQLite for DB tests where possible.

```
tests/unit/
├── test_engine.py         # ContractEngine: load, run, persist, raise
├── test_runner.py         # ContractRunner: wraps CLI correctly, normalizes output
├── test_loader.py         # ContractLoader: file, URL, git sources
├── test_drift.py          # DriftScanner: computes correct metrics from test data
├── test_baseline.py       # BaselineComputer: slope, trend, breach estimate
├── test_impact.py         # ContractDependencyGraph: edges, downstream, impact
└── test_alerting.py       # AlertDispatcher: routes to correct channels
```

### Integration Tests
Use a real PostgreSQL instance (Docker). Use `httpx.AsyncClient` for API tests.

```
tests/integration/
├── test_api.py             # All API endpoints with real DB
├── test_airflow_operator.py # SraoshaOperator in a mock DAG
└── test_dbt_hook.py        # dbt hook execution
```

### Test Fixtures
```
tests/fixtures/
├── sample_contract.yaml         # Valid contract that passes all checks
├── sample_contract_broken.yaml  # Contract with deliberate failures
└── sample_contract_drift.yaml   # Contract with drift metrics configured
```

### Running Tests
```bash
# Unit tests only
pytest tests/unit/ -v

# All tests (requires Docker for PostgreSQL)
pytest tests/ -v

# With coverage
pytest tests/ --cov=sraosha --cov-report=html
```

---

## 15. Docker & Deployment

### `docker-compose.yml` (full stack)

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: sraosha
      POSTGRES_PASSWORD: sraosha
      POSTGRES_DB: sraosha
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U sraosha"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://sraosha:sraosha@postgres:5432/sraosha
      REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    command: >
      sh -c "sraosha db upgrade && sraosha serve --host 0.0.0.0 --port 8000"

  worker:
    build:
      context: .
      dockerfile: Dockerfile
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://sraosha:sraosha@postgres:5432/sraosha
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - api
      - redis
    command: celery -A sraosha.tasks.celery_app worker --loglevel=info --beat

  dashboard:
    build:
      context: .
      dockerfile: Dockerfile.dashboard
    ports:
      - "5173:5173"
    environment:
      API_URL: http://localhost:8000

volumes:
  postgres_data:
```

### `Dockerfile` (API + worker)
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[all]"

COPY sraosha/ ./sraosha/
COPY alembic/ ./alembic/
COPY alembic.ini .

EXPOSE 8000
CMD ["sraosha", "serve", "--host", "0.0.0.0", "--port", "8000"]
```

### `Dockerfile.dashboard`
```dockerfile
FROM oven/bun:1-alpine AS builder

WORKDIR /app
COPY dashboard/package.json dashboard/bun.lockb ./
RUN bun install --frozen-lockfile

COPY dashboard/ .
RUN bun run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 5173
```

### `pyproject.toml` (key sections)

```toml
[project]
name = "sraosha"
version = "0.1.0"
description = "Enforcement and governance runtime for data contracts"
requires-python = ">=3.11"
license = { text = "MIT" }

[project.scripts]
sraosha = "sraosha.cli.main:app"

[project.dependencies]
datacontract-cli = {extras = ["all"], version = ">=0.11.0"}
fastapi = ">=0.111.0"
uvicorn = {extras = ["standard"], version = ">=0.29.0"}
sqlalchemy = {extras = ["asyncio"], version = ">=2.0.0"}
asyncpg = ">=0.29.0"
alembic = ">=1.13.0"
duckdb = ">=0.10.0"
networkx = ">=3.3"
celery = {extras = ["redis"], version = ">=5.3.0"}
pydantic-settings = ">=2.2.0"
typer = {extras = ["all"], version = ">=0.12.0"}
httpx = ">=0.27.0"
pyyaml = ">=6.0"
gitpython = ">=3.1.0"

[project.optional-dependencies]
airflow = ["apache-airflow>=2.7.0"]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "ruff>=0.4",
]
all = ["sraosha[airflow,dev]"]
```

---

## 16. README Template

The README is the most important file for open-source adoption. Use this as the template:

```markdown
# Sraosha

> The enforcement and governance runtime for data contracts.

Sraosha wraps [`datacontract-cli`](https://github.com/datacontract/datacontract-cli) to add
what the CLI cannot do on its own: **block pipelines at runtime, detect drift before breach,
map cross-contract impact, and track compliance over time.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)

## What Sraosha adds

| Feature | datacontract-cli | Sraosha |
|---|---|---|
| Define contracts in YAML | ✅ | ✅ (uses it) |
| Run quality tests on demand | ✅ | ✅ (uses it) |
| Block Airflow pipelines on violation | ❌ | ✅ |
| Block dbt runs on violation | ❌ | ✅ |
| Detect drift before threshold breach | ❌ | ✅ |
| Cross-contract impact analysis | ❌ | ✅ |
| Team compliance scoring | ❌ | ✅ |
| Self-hosted dashboard | ❌ | ✅ |

## Quickstart (60 seconds)

### 1. Start the stack
docker compose up -d

### 2. Register your first contract
sraosha register --contract contracts/orders.yaml --team my-team

### 3. Add to your Airflow DAG
from sraosha.hooks.airflow.operator import SraoshaOperator

validate = SraoshaOperator(
    task_id="validate_orders",
    contract_path="contracts/orders.yaml",
    enforcement_mode="block",
    dag=dag,
)
load_orders >> validate >> transform_orders

### 4. Check the dashboard
open http://localhost:5173

## How it works

Sraosha sits between your pipelines and your data.
When a pipeline task runs, the SraoshaOperator calls the Core Engine,
which validates the contract using datacontract-cli. If the contract fails
and enforcement_mode is "block", the pipeline aborts. Results are persisted
and visible in the dashboard.

In the background, the DriftGuard scans your datasets on a schedule and
raises warnings when metrics are trending toward a threshold — before the
contract actually breaches.

## License
MIT — use it, contribute to it, build on it.
```

---

## Notes for AI Assistants

1. **Always implement error handling.** Every function that touches external systems (DB, CLI, network) must have try/except with meaningful error messages.

2. **All async functions.** The FastAPI app is fully async. Use `async/await` throughout the API layer and database operations.

3. **Type hints everywhere.** Use Python 3.11+ type hints on all function signatures. No `Any` unless absolutely necessary.

4. **Pydantic for all data shapes.** Request bodies, response bodies, and internal data transfer objects should all be Pydantic models.

5. **Never hardcode credentials.** All secrets come from environment variables via `SraoshaSettings`.

6. **Test before moving to next phase.** Each phase must have passing unit tests before the next phase begins.

7. **Follow the build order in Section 6.** The phases have dependencies — Phase 2 requires Phase 1, Phase 4 requires Phase 1 and 2, etc.

8. **The `datacontract-cli` SDK is the engine.** Import and use `from datacontract.data_contract import DataContract`. Do not re-implement its validation logic.
```