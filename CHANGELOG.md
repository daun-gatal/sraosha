# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Core validation engine wrapping `datacontract-cli`
- Contract loader supporting local files, URLs, and Git repositories
- Airflow operator (`SraoshaOperator`) for pipeline enforcement
- dbt hook for on-run-end validation
- Drift detection module with DuckDB-based metric computation
- Statistical baseline computation with trend analysis
- Cross-contract impact analysis using dependency graphs
- FastAPI REST API with endpoints for contracts, runs, drift, compliance, and impact
- React dashboard with overview, contract detail, drift metrics, compliance, and impact map pages
- Dashboard embedded in FastAPI (single-process serving)
- Typer CLI with `run`, `status`, `history`, `drift`, `register`, `impact`, `serve`, and `db` commands
- Slack and email alerting
- Celery background tasks for periodic drift scanning and compliance computation
- Docker Compose setup for full-stack deployment
- Alembic database migrations
