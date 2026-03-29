FROM oven/bun:1-alpine AS dashboard
WORKDIR /app/dashboard
COPY dashboard/package.json dashboard/bun.lock ./
RUN bun install --frozen
COPY dashboard/ .
RUN bun run build

FROM python:3.11-slim
WORKDIR /app

COPY pyproject.toml README.md ./
COPY sraosha/ ./sraosha/
COPY --from=dashboard /app/dashboard/dist ./sraosha/static/dashboard/

RUN pip install --no-cache-dir ".[datacontract]"

COPY alembic/ ./alembic/
COPY alembic.ini .

EXPOSE 8000
CMD ["sraosha", "serve", "--host", "0.0.0.0", "--port", "8000"]
