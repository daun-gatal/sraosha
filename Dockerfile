FROM python:3.11-slim
WORKDIR /app

COPY pyproject.toml README.md ./
COPY sraosha/ ./sraosha/
COPY alembic/ ./alembic/
COPY alembic.ini .

RUN pip install --no-cache-dir . \
    soda-core==3.5.6 \
    soda-core-postgres==3.5.6

EXPOSE 8000
CMD ["sraosha", "serve", "--host", "0.0.0.0", "--port", "8000"]
