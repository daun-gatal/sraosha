.DEFAULT_GOAL := help
# Dev: make sync && make db && make start  —  make stop

.PHONY: help sync db start stop serve frontend lint fix test clean

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

sync: ## Install Python deps (uv)
	uv sync --extra dev

db: ## Alembic upgrade head
	uv run sraosha db

start: ## Build SPA; API + worker + beat in background (.sraosha-start.*)
	@$(MAKE) stop
	cd frontend && bun install && bun run build && cd ..
	@bash -c 'rm -f .sraosha-start.pids .sraosha-start-api.log .sraosha-start-worker.log .sraosha-start-beat.log; \
		nohup uv run sraosha serve --reload >> .sraosha-start-api.log 2>&1 & echo $$! >> .sraosha-start.pids; \
		nohup uv run sraosha worker --loglevel info >> .sraosha-start-worker.log 2>&1 & echo $$! >> .sraosha-start.pids; \
		nohup uv run sraosha beat --loglevel info >> .sraosha-start-beat.log 2>&1 & echo $$! >> .sraosha-start.pids; \
		echo "Started — .sraosha-start.pids — make stop"'

stop: ## Kill .sraosha-start PIDs + :8000 / :5173
	@if [ -f .sraosha-start.pids ]; then \
		while read -r pid; do [ -n "$$pid" ] && kill "$$pid" 2>/dev/null || true; done < .sraosha-start.pids; \
		rm -f .sraosha-start.pids; fi
	@for port in 8000 5173; do \
		p=$$(lsof -ti "tcp:$$port" -sTCP:LISTEN 2>/dev/null || true); \
		[ -n "$$p" ] && kill $$p 2>/dev/null || true; done
	@rm -f .dev-all.pids

serve: ## Build SPA; API foreground (reload)
	cd frontend && bun install && bun run build && cd .. && uv run sraosha serve --reload

frontend: ## Vite dev (:5173, proxies /api)
	cd frontend && bun install && bun run dev

lint: ## Ruff check + format --check
	uv run ruff check sraosha/ tests/ && uv run ruff format --check sraosha/ tests/

fix: ## Ruff format + auto-fix
	uv run ruff format sraosha/ tests/ && uv run ruff check --fix sraosha/ tests/

test: ## Pytest (unit + integration)
	uv run pytest tests/ -v

clean: ## Caches, egg-info, start logs
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .ruff_cache/ .mypy_cache/ htmlcov/ .coverage
	rm -f .sraosha-start.pids .sraosha-start-api.log .sraosha-start-worker.log .sraosha-start-beat.log
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
