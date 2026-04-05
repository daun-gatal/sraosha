"""Schema introspection using saved Connection credentials (sync; use via asyncio.to_thread)."""

from __future__ import annotations

import logging
from typing import Any

from sraosha.api.introspect import SUPPORTED_TYPES, get_introspector
from sraosha.crypto import decrypt
from sraosha.models.connection import Connection

logger = logging.getLogger(__name__)


def _password(c: Connection) -> str:
    if c.password_encrypted:
        return decrypt(c.password_encrypted)
    return ""


def introspection_kwargs_for_connection(c: Connection) -> tuple[str, dict[str, Any]]:
    """Return (normalized_server_type, kwargs) for get_introspector, or raise ValueError."""
    st = (c.server_type or "").strip().lower()
    if st in ("postgresql", "cloudsql"):
        st = "postgres"
    if st == "clickhouse":
        st = "mysql"
    if st not in SUPPORTED_TYPES:
        raise ValueError(
            f"Introspection not supported for server type {c.server_type!r}. "
            f"Supported: {', '.join(SUPPORTED_TYPES)}"
        )

    if st == "postgres":
        return st, {
            "host": c.host or "localhost",
            "port": int(c.port or 5432),
            "database": c.database or "postgres",
            "user": c.username or "postgres",
            "password": _password(c),
        }
    if st == "mysql":
        return st, {
            "host": c.host or "localhost",
            "port": int(c.port or 3306),
            "database": c.database or "",
            "user": c.username or "root",
            "password": _password(c),
        }
    if st == "duckdb":
        return st, {
            "path": c.path or ":memory:",
            "database": c.database or "",
        }
    raise ValueError(f"Unsupported server type {st!r}")


def default_schema_for_connection(c: Connection) -> str:
    st = (c.server_type or "").strip().lower()
    if st in ("postgresql", "cloudsql"):
        st = "postgres"
    if st == "clickhouse":
        st = "mysql"
    if st == "postgres":
        return (c.schema_name or "public").strip() or "public"
    if st == "mysql":
        return (c.schema_name or "").strip()
    if st == "duckdb":
        return "main"
    return "public"


def list_tables_sync(c: Connection, schema: str | None) -> tuple[str, list[dict[str, str]]]:
    """Returns (schema_used, list of {table_name, table_type})."""
    st, kwargs = introspection_kwargs_for_connection(c)
    schema_used = (schema or "").strip() or default_schema_for_connection(c)
    intro = get_introspector(st, **kwargs)
    try:
        rows = intro.list_tables(schema_used)
    finally:
        intro.close()
    return schema_used, rows


def list_columns_sync(
    c: Connection, schema: str | None, table: str
) -> tuple[str, list[dict[str, Any]]]:
    st, kwargs = introspection_kwargs_for_connection(c)
    schema_used = (schema or "").strip() or default_schema_for_connection(c)
    tbl = (table or "").strip()
    if not tbl:
        raise ValueError("table name is required")
    intro = get_introspector(st, **kwargs)
    try:
        cols = intro.get_columns(schema_used, tbl)
    finally:
        intro.close()
    return schema_used, cols


def connection_id_to_name_map(c: Connection) -> dict[str, str]:
    return {str(c.id): c.name}
