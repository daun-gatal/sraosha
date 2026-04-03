"""Synchronous database helper for Celery tasks.

Celery workers are synchronous, so we use psycopg2 directly
instead of the async SQLAlchemy engine used by the FastAPI app.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

import psycopg2
import psycopg2.extras

from sraosha.config import settings

psycopg2.extras.register_uuid()


def _sync_dsn() -> str:
    url = settings.DATABASE_URL
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


@contextmanager
def get_sync_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    conn = psycopg2.connect(_sync_dsn())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
