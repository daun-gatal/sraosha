.DEFAULT_GOAL := help

.PHONY: help lint format test test-all typecheck dev clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

lint: ## Run linter checks
	ruff check sraosha/ tests/
	ruff format --check sraosha/ tests/

format: ## Auto-format code
	ruff format sraosha/ tests/
	ruff check --fix sraosha/ tests/

test: ## Run unit tests
	pytest tests/unit/ -v

test-all: ## Run all tests (requires Docker services)
	pytest tests/ -v

test-cov: ## Run tests with coverage
	pytest tests/unit/ -v --cov=sraosha --cov-report=html

typecheck: ## Run type checker
	mypy sraosha/

dev: ## Start full stack with Docker Compose
	docker-compose up --build

dev-api: ## Start API server for development (templates hot-reload)
	sraosha serve --reload

clean: ## Remove build artifacts and caches
	rm -rf build/ dist/ *.egg-info/
	rm -rf .pytest_cache/ .ruff_cache/ .mypy_cache/ htmlcov/ .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
