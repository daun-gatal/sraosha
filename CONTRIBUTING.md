# Contributing to Sraosha

Thank you for your interest in contributing to Sraosha! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- PostgreSQL and Redis (local install or any reachable instance; optional Docker Compose only if you want containers)
- [Bun](https://bun.sh/) (for the SPA)

### Getting Started

```bash
git clone https://github.com/YOUR_ORG/sraosha.git
cd sraosha

make sync
# or: uv sync --extra dev

uv run pre-commit install

cp .sraosha.example .sraosha
# Edit .sraosha: DATABASE_URL and REDIS_URL must point at your Postgres and Redis.

make db
make start
```

**`make start`** builds the SPA and starts the API (serves the built UI on :8000), a Celery **worker**, and **beat** in the background, with PIDs in `.sraosha-start.pids` and logs `.sraosha-start-*.log`. **`make stop`** stops those processes and anything listening on :8000 or :5173. **`make serve`** is the same build + API in the **foreground** (no worker/beat). Use **`make help`** for other targets (`frontend`, `lint`, …).

### Web UI (React)

The SPA lives in `frontend/` (Bun + Vite). `make start` / `make serve` run `bun install` and `bun run build` before `sraosha serve`. Use `make frontend` for Vite-only dev on :5173. The API serves the built app under `/app/` when `frontend/dist/` exists.

## Running Tests

```bash
make test
# or: uv run pytest tests/unit/ -v   # faster subset
```

## Code Quality

```bash
make lint          # ruff check + format --check
make fix           # ruff format + --fix
uv run mypy sraosha/
```

## Making Changes

1. Fork the repository and create a feature branch from `main`.
2. Make your changes. Add tests for new functionality.
3. Ensure checks pass: `make lint && make test && uv run mypy sraosha/`
4. Commit your changes with a clear, descriptive message.
5. Push your branch and open a pull request against `main`. CI (lint, type check, tests, package build, optional Docker build test when relevant paths change, Grype) runs on the PR. Publishing to PyPI and GHCR happens via the **Release** workflow when `CHANGELOG.md` / `Dockerfile` on `main` include a new version (see project maintainers’ release process).

## Code Style

- Python code follows [Ruff](https://docs.astral.sh/ruff/) defaults with a 100-character line length.
- Use type hints on all function signatures.
- Use Pydantic models for data shapes.
- Write async code in the API layer.
- All configuration comes from environment variables via `SraoshaSettings`.

## Pull Request Guidelines

- Keep PRs focused on a single concern.
- Include tests for new features and bug fixes.
- Update documentation if your changes affect user-facing behavior.
- Ensure CI passes before requesting review.

## Reporting Issues

Use [GitHub Issues](https://github.com/YOUR_ORG/sraosha/issues) to report bugs or suggest features. Please include:

- Steps to reproduce (for bugs)
- Expected vs actual behavior
- Python version and OS
- Relevant logs or error messages
