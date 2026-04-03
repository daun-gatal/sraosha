# Sraosha

> The enforcement and governance runtime for data contracts.

Sraosha wraps [`datacontract-cli`](https://github.com/datacontract/datacontract-cli) to add
what the CLI cannot do on its own: **enforce contracts from the CLI and API, run optional
Soda-based data quality checks against your databases, map cross-contract impact, and track
compliance over time** — with a self-hosted dashboard on the same port as the API.

[![CI](https://github.com/YOUR_ORG/sraosha/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_ORG/sraosha/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)

Replace `YOUR_ORG` in the badge URLs with your GitHub org or user when you fork.

The CI badge reflects the **CI** workflow (lint, tests, package build, optional Docker build test, Grype), which runs on **pull requests** to `main`. The **Release** workflow runs when **`CHANGELOG.md` or `Dockerfile`** changes on `main`: it creates the git tag and GitHub Release from the changelog, **publishes to PyPI**, and **builds and pushes** `ghcr.io/…` images when code-related paths changed in that push.

## Table of Contents

- [What Sraosha Adds](#what-sraosha-adds)
- [Installation](#installation)
- [Quickstart](#quickstart)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Architecture (detailed)](ARCHITECTURE.md)
- [CLI Commands](#cli-commands)
- [Configuration](#configuration)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## What Sraosha Adds

| Feature | datacontract-cli | Sraosha |
|---|---|---|
| Define contracts in YAML | Yes | Yes (uses it) |
| Run quality tests on demand | Yes | Yes (uses it) |
| Enforce contracts (CLI / API / embedded engine) | Manual only | Yes |
| Optional DB data quality checks (Soda Core) | No | Yes |
| Cross-contract impact analysis | No | Yes |
| Team compliance scoring | No | Yes |
| Self-hosted dashboard | No | Yes (Jinja2 + FastAPI) |

Install **Soda Core** (and a connector such as `soda-core-postgres`) when you want data-quality features; the base package focuses on contract validation and governance UI.

## Installation

```bash
pip install sraosha
```

Development dependencies (tests, lint, types):

```bash
pip install -e ".[dev]"
```

## Quickstart

### Using Docker Compose (recommended)

```bash
# Copy and edit the config file
cp .sraosha.example .sraosha

# Full stack: API + PostgreSQL + Redis + Celery worker + Celery beat
docker compose up -d

# Open the dashboard
open http://localhost:8000/ui/
```

### Using pip

```bash
# Install
pip install sraosha

# Create a config file (or set env vars directly)
cp .sraosha.example .sraosha

# Start the API server (dashboard included)
sraosha serve
```

You can also point to a custom config path:

```bash
sraosha --config /etc/sraosha/.sraosha serve
# or
SRAOSHA_CONFIG=/etc/sraosha/.sraosha sraosha serve
```

### Register and validate a contract

```bash
# Register a contract
sraosha register --contract contracts/orders.yaml --team my-team

# Run validation
sraosha run --contract contracts/orders.yaml --mode block
```

## How It Works

You run validation from the CLI (`sraosha run`), the API, or by embedding
[`ContractEngine`](sraosha/core/engine.py) in your own jobs or services. The engine validates with
`datacontract-cli`. If enforcement is `block` and checks fail, the process
exits with an error (CLI) or raises (Python); results are persisted when a
database is configured and visible in the dashboard.

**Background processing:** Celery **beat** schedules periodic tasks (daily compliance score
recompute, validation schedule polling, DQ schedule polling). Celery **workers** execute those
tasks. See [ARCHITECTURE.md](ARCHITECTURE.md) for the exact task list.

**Data quality:** Optional Soda-based checks are configured per connection and exposed under
`/api/v1/data-quality`; they complement contract validation rather than replacing it.

The **Lineage** page (`/ui/impact`) visualizes contract dependencies: focus a
contract with optional upstream/downstream hop limits, inspect edges for column
mappings, and run impact analysis from the side panel. The API exposes
`GET /api/v1/impact/graph` (full graph) and
`GET /api/v1/impact/lineage/{contract_id}?upstream_depth=&downstream_depth=`
(subgraph). Each node includes a **platform** string from the first
`servers.*.type` entry in the contract YAML (DataHub-style cards use a colored
accent per platform).

## Architecture

For diagrams, API prefixes, Celery topology, and package layout, see **[ARCHITECTURE.md](ARCHITECTURE.md)**.

At a glance:

- **FastAPI** serves JSON under `/api/v1/*`, the Jinja2 dashboard under `/ui/*`, and OpenAPI at `/docs`.
- **PostgreSQL** stores contracts, runs, teams, schedules, DQ metadata, and compliance scores.
- **Redis** backs Celery; run **one** `sraosha beat` and **one or more** `sraosha worker` processes in production.

```
Orchestrator / job / CLI / API
         |
         v
  ContractEngine --> datacontract-cli (validation)
         |
         +--> PostgreSQL (persisted runs, contracts, scores, ...)
         |
         v
  FastAPI (:8000)  +  Celery workers (scheduled jobs)
```

## CLI Commands

```bash
sraosha [--config PATH] <command>

sraosha run --contract path/to/contract.yaml [--mode block|warn|log] [--server NAME]
sraosha status [--format table|json]
sraosha history --contract <contract_id> [--limit 20]
sraosha register --contract path/to/contract.yaml --team my-team
sraosha impact --contract <contract_id> --fields field_a,field_b
sraosha serve [--host 0.0.0.0] [--port 8000] [--reload]
sraosha db                    # Alembic: upgrade database to head
sraosha worker [--loglevel info] [--concurrency 4] [--hostname worker@%h]
sraosha beat [--loglevel info]
sraosha version
```

**Compliance snapshots (Docker):** the stack runs separate `worker` and `beat` services. To trigger a one-off write to `compliance_scores` without waiting for the daily schedule:

```bash
docker compose exec worker celery -A sraosha.tasks.celery_app call \
  sraosha.tasks.compliance_compute.compute_compliance_scores
```

## Configuration

Sraosha reads configuration from a `.sraosha` file (dotenv format).

**Resolution order** (first match wins):

1. `--config PATH` CLI flag
2. `SRAOSHA_CONFIG` environment variable
3. `.sraosha` in the current working directory
4. `~/.sraosha` in your home directory
5. Built-in defaults

Environment variables always override file values. See `.sraosha.example` for all available settings.

## Development

```bash
# Clone and set up
git clone https://github.com/YOUR_ORG/sraosha.git
cd sraosha

# Install with uv (recommended)
uv sync --extra dev

# Or with pip
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Start infrastructure
docker compose up postgres redis -d

# Apply migrations, then run API locally (templates hot-reload with --reload)
uv run sraosha db
uv run sraosha serve --reload
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full development guide.

### Make Targets

```bash
make lint             # Ruff check + format check
make format           # Auto-format code
make test             # Unit tests
make test-cov         # Tests with coverage
make typecheck        # mypy
make dev              # Docker Compose full stack
make clean            # Remove caches and build artifacts
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT -- see [LICENSE](LICENSE) for details.
