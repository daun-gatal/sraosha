FROM python:3.11-slim

ARG VERSION=unknown
ARG COMMIT_SHA=unknown
ARG BUILD_DATE=unknown

LABEL org.opencontainers.image.title="sraosha" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${COMMIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}"

WORKDIR /app

COPY pyproject.toml README.md ./
COPY sraosha/ ./sraosha/
COPY alembic/ ./alembic/
COPY alembic.ini .

RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["sraosha", "serve", "--host", "0.0.0.0", "--port", "8000"]
