# Sraosha

> The enforcement and governance runtime for data contracts.

Sraosha wraps [`datacontract-cli`](https://github.com/datacontract/datacontract-cli) to add
what the CLI cannot do on its own: **block pipelines at runtime, detect drift before breach,
map cross-contract impact, and track compliance over time.**

[![CI](https://github.com/YOUR_ORG/sraosha/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_ORG/sraosha/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)

## Table of Contents

- [What Sraosha Adds](#what-sraosha-adds)
- [Installation](#installation)
- [Quickstart](#quickstart)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [CLI Commands](#cli-commands)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## What Sraosha Adds

| Feature | datacontract-cli | Sraosha |
|---|---|---|
| Define contracts in YAML | Yes | Yes (uses it) |
| Run quality tests on demand | Yes | Yes (uses it) |
| Block Airflow pipelines on violation | No | Yes |
| Block dbt runs on violation | No | Yes |
| Detect drift before threshold breach | No | Yes |
| Cross-contract impact analysis | No | Yes |
| Team compliance scoring | No | Yes |
| Self-hosted dashboard | No | Yes |

## Installation

```bash
pip install sraosha
```

Or with optional integrations:

```bash
pip install sraosha[datacontract]     # Include datacontract-cli
pip install sraosha[airflow]          # Include Airflow provider
pip install sraosha[all]              # Everything
```

## Quickstart

### Using Docker Compose (recommended)

```bash
# Start the full stack (API + dashboard + PostgreSQL + Redis)
docker compose up -d

# Open the dashboard
open http://localhost:8000
```

### Using pip

```bash
# Install
pip install sraosha[datacontract]

# Start the API server (dashboard included)
sraosha serve
```

### Register and validate a contract

```bash
# Register a contract
sraosha register --contract contracts/orders.yaml --team my-team

# Run validation
sraosha run --contract contracts/orders.yaml --mode block
```

### Add to your Airflow DAG

```python
from sraosha.hooks.airflow.operator import SraoshaOperator

validate = SraoshaOperator(
    task_id="validate_orders",
    contract_path="contracts/orders.yaml",
    enforcement_mode="block",
    dag=dag,
)
load_orders >> validate >> transform_orders
```

## How It Works

Sraosha sits between your pipelines and your data.
When a pipeline task runs, the SraoshaOperator calls the Core Engine,
which validates the contract using datacontract-cli. If the contract fails
and enforcement_mode is "block", the pipeline aborts. Results are persisted
and visible in the dashboard.

In the background, the DriftGuard scans your datasets on a schedule and
raises warnings when metrics are trending toward a threshold -- before the
contract actually breaches.

## Architecture

```
Pipeline (Airflow / dbt / CLI / API)
    |
    v
Sraosha Hook --> Core Engine --> datacontract-cli (validation)
    |                 |
    |                 v
    |           DriftGuard (statistical trends via DuckDB)
    |                 |
    v                 v
PostgreSQL <--- Results persisted
    |
    v
FastAPI (REST API + embedded React dashboard)
    :8000/api/v1/*   -- API endpoints
    :8000/*           -- Dashboard UI
```

The dashboard is embedded in the FastAPI process -- a single `sraosha serve` command
gives you both the API and the web UI on one port.

## CLI Commands

```bash
sraosha run --contract path/to/contract.yaml [--mode block|warn|log]
sraosha status [--format table|json]
sraosha history --contract <contract_id> [--limit 20]
sraosha drift --contract <contract_id>
sraosha register --contract path/to/contract.yaml --team my-team
sraosha impact --contract <contract_id> --fields field_a,field_b
sraosha serve [--host 0.0.0.0] [--port 8000] [--reload]
sraosha db upgrade
sraosha version
```

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

# Run API locally
sraosha serve --reload

# Run dashboard dev server (hot reload)
cd dashboard && bun dev
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full development guide.

### Make Targets

```bash
make lint             # Ruff check + format check
make format           # Auto-format code
make test             # Unit tests
make test-cov         # Tests with coverage
make typecheck        # mypy
make build-dashboard  # Build dashboard static files
make dev              # Docker Compose full stack
make clean            # Remove caches and build artifacts
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT -- see [LICENSE](LICENSE) for details.
