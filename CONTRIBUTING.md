# Contributing to Sraosha

Thank you for your interest in contributing to Sraosha! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Docker and Docker Compose (for running the full stack)

### Getting Started

```bash
# Clone the repository
git clone https://github.com/YOUR_ORG/sraosha.git
cd sraosha

# Create a virtual environment and install dependencies
uv sync --extra dev

# Install pre-commit hooks
uv run pre-commit install

# Copy the config file
cp .sraosha.example .sraosha

# Start infrastructure (PostgreSQL + Redis)
docker compose up postgres redis -d

# Run database migrations
uv run sraosha db upgrade

# Start the API server
uv run sraosha serve --reload
```

### Dashboard Templates

The dashboard UI is built with Jinja2 templates in `sraosha/api/templates/`. When running the API with `--reload`, template changes are picked up automatically on page refresh -- no separate build step is needed.

## Running Tests

```bash
# Unit tests
uv run pytest tests/unit/ -v

# Unit tests with coverage
uv run pytest tests/unit/ -v --cov=sraosha --cov-report=html

# All tests (requires Docker services running)
uv run pytest tests/ -v
```

## Code Quality

```bash
# Lint
uv run ruff check sraosha/ tests/

# Format
uv run ruff format sraosha/ tests/

# Type check
uv run mypy sraosha/

# Or use Make targets
make lint
make format
make typecheck
```

## Making Changes

1. Fork the repository and create a feature branch from `main`.
2. Make your changes. Add tests for new functionality.
3. Ensure all checks pass: `make lint && make test && make typecheck`
4. Commit your changes with a clear, descriptive message.
5. Push your branch and open a pull request.

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
