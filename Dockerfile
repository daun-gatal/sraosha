# syntax=docker/dockerfile:1
# Single image: API + Celery + built React SPA (served under `/app/` by FastAPI).

FROM node:22-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

ARG VERSION=unknown
ARG COMMIT_SHA=unknown
ARG BUILD_DATE=unknown

LABEL org.opencontainers.image.title="sraosha" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${COMMIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}"

WORKDIR /app

# Install deps from uv.lock so the resolver does not backtrack (slow `pip install` with loose
# google-* constraints). Same graph as `uv sync` locally.
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY sraosha/ ./sraosha/

RUN uv sync --frozen --no-dev

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

COPY --from=frontend-build /build/dist ./frontend/dist

EXPOSE 8000
CMD ["sraosha", "serve", "--host", "0.0.0.0", "--port", "8000"]
