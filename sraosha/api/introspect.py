"""Database introspection for auto-discovering tables and generating contracts.

Supports SQL sources that expose information_schema (Postgres, MySQL, DuckDB).
Extensible via the SchemaIntrospector ABC.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

SUPPORTED_TYPES = ("postgres", "mysql", "duckdb")


class SchemaIntrospector(ABC):
    """Base class for database schema introspection."""

    @abstractmethod
    def test_connection(self) -> bool:
        """Return True if the connection succeeds."""

    @abstractmethod
    def list_tables(self, schema: str = "public") -> list[dict[str, str]]:
        """Return list of dicts with keys: table_name, table_type ('table'|'view')."""

    @abstractmethod
    def get_columns(self, schema: str, table: str) -> list[dict[str, Any]]:
        """Return list of dicts with keys: column_name, data_type, is_nullable, ordinal_position."""

    @abstractmethod
    def close(self) -> None:
        """Release the underlying connection."""

    def discover(self, schema: str = "public") -> list[dict[str, Any]]:
        """Discover all tables in a schema with their columns."""
        tables = self.list_tables(schema)
        result = []
        for tbl in tables:
            cols = self.get_columns(schema, tbl["table_name"])
            result.append({**tbl, "columns": cols})
        return result


class PostgresIntrospector(SchemaIntrospector):
    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        import psycopg2

        self._conn = psycopg2.connect(
            host=host, port=port, dbname=database, user=user, password=password
        )
        self._conn.set_session(readonly=True, autocommit=True)

    def test_connection(self) -> bool:
        try:
            with self._conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            return False

    def list_tables(self, schema: str = "public") -> list[dict[str, str]]:
        with self._conn.cursor() as cur:
            cur.execute(
                """SELECT table_name, table_type
                   FROM information_schema.tables
                   WHERE table_schema = %s
                     AND table_type IN ('BASE TABLE', 'VIEW')
                   ORDER BY table_name""",
                (schema,),
            )
            return [
                {"table_name": r[0], "table_type": "view" if r[1] == "VIEW" else "table"}
                for r in cur.fetchall()
            ]

    def get_columns(self, schema: str, table: str) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute(
                """SELECT column_name, data_type, is_nullable, ordinal_position
                   FROM information_schema.columns
                   WHERE table_schema = %s AND table_name = %s
                   ORDER BY ordinal_position""",
                (schema, table),
            )
            return [
                {
                    "column_name": r[0],
                    "data_type": r[1],
                    "is_nullable": r[2] == "YES",
                    "ordinal_position": r[3],
                }
                for r in cur.fetchall()
            ]

    def close(self) -> None:
        self._conn.close()


class MySQLIntrospector(SchemaIntrospector):
    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        try:
            import pymysql
        except ImportError as exc:
            raise ImportError(
                "pymysql is required for MySQL introspection. "
                "Install it with: pip install 'sraosha[mysql]'"
            ) from exc
        self._conn = pymysql.connect(
            host=host, port=port, database=database, user=user, password=password
        )

    def test_connection(self) -> bool:
        try:
            with self._conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            return False

    def list_tables(self, schema: str = "") -> list[dict[str, str]]:
        with self._conn.cursor() as cur:
            cur.execute(
                """SELECT table_name, table_type
                   FROM information_schema.tables
                   WHERE table_schema = DATABASE()
                     AND table_type IN ('BASE TABLE', 'VIEW')
                   ORDER BY table_name"""
            )
            return [
                {"table_name": r[0], "table_type": "view" if r[1] == "VIEW" else "table"}
                for r in cur.fetchall()
            ]

    def get_columns(self, schema: str, table: str) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute(
                """SELECT column_name, data_type, is_nullable, ordinal_position
                   FROM information_schema.columns
                   WHERE table_schema = DATABASE() AND table_name = %s
                   ORDER BY ordinal_position""",
                (table,),
            )
            return [
                {
                    "column_name": r[0],
                    "data_type": r[1],
                    "is_nullable": r[2] == "YES",
                    "ordinal_position": r[3],
                }
                for r in cur.fetchall()
            ]

    def close(self) -> None:
        self._conn.close()


class DuckDBIntrospector(SchemaIntrospector):
    def __init__(self, path: str = ":memory:", database: str = "", **_: Any):
        try:
            import duckdb
        except ImportError:
            raise ImportError(
                "duckdb is required for DuckDB schema introspection. "
                "Install it with: pip install duckdb"
            ) from None

        self._conn = duckdb.connect(path, read_only=True)

    def test_connection(self) -> bool:
        try:
            self._conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def list_tables(self, schema: str = "main") -> list[dict[str, str]]:
        rows = self._conn.execute(
            """SELECT table_name, table_type
               FROM information_schema.tables
               WHERE table_schema = ?
                 AND table_type IN ('BASE TABLE', 'VIEW', 'LOCAL TEMPORARY')
               ORDER BY table_name""",
            [schema],
        ).fetchall()
        return [
            {"table_name": r[0], "table_type": "view" if "VIEW" in r[1] else "table"} for r in rows
        ]

    def get_columns(self, schema: str, table: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT column_name, data_type, is_nullable, ordinal_position
               FROM information_schema.columns
               WHERE table_schema = ? AND table_name = ?
               ORDER BY ordinal_position""",
            [schema, table],
        ).fetchall()
        return [
            {
                "column_name": r[0],
                "data_type": r[1],
                "is_nullable": r[2] == "YES",
                "ordinal_position": r[3],
            }
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()


PG_TYPE_MAP: dict[str, str] = {
    "integer": "integer",
    "bigint": "integer",
    "smallint": "integer",
    "int": "integer",
    "int4": "integer",
    "int8": "integer",
    "serial": "integer",
    "bigserial": "integer",
    "numeric": "float",
    "decimal": "float",
    "real": "float",
    "double precision": "float",
    "float": "float",
    "float4": "float",
    "float8": "float",
    "boolean": "boolean",
    "bool": "boolean",
    "text": "text",
    "varchar": "text",
    "character varying": "text",
    "char": "text",
    "character": "text",
    "name": "text",
    "uuid": "uuid",
    "timestamp without time zone": "timestamp",
    "timestamp with time zone": "timestamp",
    "timestamp": "timestamp",
    "timestamptz": "timestamp",
    "date": "date",
    "json": "json",
    "jsonb": "json",
    "bytea": "binary",
    "array": "array",
    "ARRAY": "array",
}


def _map_type(raw_type: str) -> str:
    """Map a database-native type to a data contract field type."""
    raw = raw_type.lower().strip()
    if raw in PG_TYPE_MAP:
        return PG_TYPE_MAP[raw]
    if "int" in raw:
        return "integer"
    if "char" in raw or "text" in raw:
        return "text"
    if "float" in raw or "double" in raw or "numeric" in raw or "decimal" in raw:
        return "float"
    if "bool" in raw:
        return "boolean"
    if "time" in raw:
        return "timestamp"
    if "date" in raw:
        return "date"
    if "json" in raw:
        return "json"
    if "uuid" in raw:
        return "uuid"
    if "byte" in raw or "blob" in raw or "binary" in raw:
        return "binary"
    return "text"


def get_introspector(server_type: str, **params: Any) -> SchemaIntrospector:
    """Factory that returns the right introspector for a given server type."""
    if server_type == "postgres":
        return PostgresIntrospector(
            host=params.get("host", "localhost"),
            port=int(params.get("port", 5432)),
            database=params.get("database", "postgres"),
            user=params.get("user", "postgres"),
            password=params.get("password", ""),
        )
    if server_type == "mysql":
        return MySQLIntrospector(
            host=params.get("host", "localhost"),
            port=int(params.get("port", 3306)),
            database=params.get("database", ""),
            user=params.get("user", "root"),
            password=params.get("password", ""),
        )
    if server_type == "duckdb":
        return DuckDBIntrospector(
            path=params.get("path", ":memory:"),
            database=params.get("database", ""),
        )
    raise ValueError(
        f"Introspection not yet supported for '{server_type}'. "
        f"Supported types: {', '.join(SUPPORTED_TYPES)}"
    )
