from __future__ import annotations

import re
from typing import Any

import yaml

SODA_TYPE_MAP: dict[str, str] = {
    "postgres": "postgres",
    "mysql": "mysql",
    "bigquery": "bigquery",
    "snowflake": "snowflake",
    "redshift": "redshift",
    "databricks": "spark",
    "trino": "trino",
    "duckdb": "duckdb",
    "mssql": "sqlserver",
    "athena": "athena",
    "clickhouse": "clickhouse",
    "oracle": "oracle",
    "vertica": "vertica",
    "presto": "presto",
    "synapse": "synapse",
    "denodo": "denodo",
    "dremio": "dremio",
    "motherduck": "motherduck",
    "db2": "db2",
    "spark": "spark",
    "fabric": "fabric",
    "cloudsql": "postgres",
    "dask": "dask",
    "postgresql": "postgres",
}

SODA_CONNECTOR_TYPES: frozenset[str] = frozenset(SODA_TYPE_MAP.values())

_DATA_SOURCE_NAME_RE = re.compile(r"^[a-z_][a-z_0-9]+$")


def sanitize_data_source_name(name: str) -> str:
    s = "".join(c if (c.isascii() and (c.isalnum() or c == "_")) else "_" for c in name.lower())
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "data_source"
    if s[0].isdigit():
        s = f"ds_{s}"
    if len(s) < 2:
        s = f"{s}_x"
    if not _DATA_SOURCE_NAME_RE.match(s):
        s = "data_source"
    return s


def soda_connector_type_for_server_type(server_type: str) -> str:
    key = (server_type or "").strip().lower()
    return SODA_TYPE_MAP.get(key, "postgres")


def resolve_data_source_name(
    server_type: str, explicit: str | None
) -> tuple[str, str | None]:
    """Resolve the Soda scan data source key. Returns (name, error_message_or_none)."""
    raw = (explicit or "").strip()
    if raw:
        if raw not in SODA_CONNECTOR_TYPES:
            return (
                "",
                f"Invalid Soda connector type {raw!r}. Choose a supported type from the list.",
            )
        return sanitize_data_source_name(raw), None
    mapped = soda_connector_type_for_server_type(server_type)
    return sanitize_data_source_name(mapped), None


def explicit_data_source_for_form(stored: str, server_type: str) -> str:
    """Value for the connector dropdown; empty means use connection default."""
    s = (stored or "").strip()
    if not s:
        return ""
    default_name, _ = resolve_data_source_name(server_type, "")
    if s == default_name:
        return ""
    if s in SODA_CONNECTOR_TYPES:
        return s
    return ""


def _omit_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _port_int(conn_params: dict) -> int | None:
    p = conn_params.get("port")
    if p is None or p == "":
        return None
    return int(p)


def _build_connection_dict(soda_type: str, conn_params: dict) -> dict[str, Any]:
    host = conn_params.get("host")
    port = _port_int(conn_params)
    database = conn_params.get("database")
    schema = conn_params.get("schema")
    username = conn_params.get("username")
    password = conn_params.get("password")
    account = conn_params.get("account")
    warehouse = conn_params.get("warehouse")
    role = conn_params.get("role")
    catalog = conn_params.get("catalog")
    http_path = conn_params.get("httpPath")
    project = conn_params.get("project")
    dataset = conn_params.get("dataset")
    token = conn_params.get("token")
    service_account_json = conn_params.get("service_account_json")
    path = conn_params.get("path")
    location = conn_params.get("location")

    if soda_type == "postgres":
        return _omit_none(
            {
                "type": "postgres",
                "host": host,
                "port": port,
                "username": username,
                "password": password,
                "database": database,
                "schema": schema,
            }
        )
    if soda_type == "mysql":
        return _omit_none(
            {
                "type": "mysql",
                "host": host,
                "port": port or 3306,
                "username": username,
                "password": password,
                "database": database,
            }
        )
    if soda_type == "bigquery":
        cfg = _omit_none(
            {
                "type": "bigquery",
                "account_info_json": service_account_json,
                "project_id": project,
                "dataset": dataset,
                "location": location,
            }
        )
        return cfg
    if soda_type == "snowflake":
        return _omit_none(
            {
                "type": "snowflake",
                "account": account,
                "username": username,
                "password": password,
                "warehouse": warehouse,
                "database": database,
                "schema": schema,
                "role": role,
            }
        )
    if soda_type == "redshift":
        return _omit_none(
            {
                "type": "redshift",
                "host": host,
                "port": port or 5439,
                "username": username,
                "password": password,
                "database": database,
            }
        )
    if soda_type == "spark":
        return _omit_none(
            {
                "type": "spark",
                "host": host,
                "http_path": http_path,
                "token": token,
                "catalog": catalog,
                "database": database,
                "schema": schema,
            }
        )
    if soda_type == "trino":
        return _omit_none(
            {
                "type": "trino",
                "host": host,
                "port": port or 8080,
                "username": username,
                "password": password,
                "catalog": catalog,
                "schema": schema,
            }
        )
    if soda_type == "duckdb":
        return _omit_none({"type": "duckdb", "path": path or database, "schema": schema})
    if soda_type == "sqlserver":
        return _omit_none(
            {
                "type": "sqlserver",
                "host": host,
                "port": port or 1433,
                "username": username,
                "password": password,
                "database": database,
                "schema": schema,
            }
        )
    if soda_type == "athena":
        return _omit_none(
            {
                "type": "athena",
                "region_name": conn_params.get("region") or location,
                "database": database,
                "s3_staging_dir": conn_params.get("s3_staging_dir"),
                "schema": schema,
            }
        )
    if soda_type == "clickhouse":
        return _omit_none(
            {
                "type": "clickhouse",
                "host": host,
                "port": port or 8123,
                "username": username,
                "password": password,
                "database": database,
            }
        )
    if soda_type == "oracle":
        return _omit_none(
            {
                "type": "oracle",
                "host": host,
                "port": port or 1521,
                "username": username,
                "password": password,
                "database": database,
            }
        )
    if soda_type == "vertica":
        return _omit_none(
            {
                "type": "vertica",
                "host": host,
                "port": port or 5433,
                "username": username,
                "password": password,
                "database": database,
                "schema": schema,
            }
        )
    if soda_type == "presto":
        return _omit_none(
            {
                "type": "presto",
                "host": host,
                "port": port or 8080,
                "username": username,
                "password": password,
                "catalog": catalog,
                "schema": schema,
            }
        )
    if soda_type == "synapse":
        return _omit_none(
            {
                "type": "synapse",
                "host": host,
                "port": port or 1433,
                "username": username,
                "password": password,
                "database": database,
                "schema": schema,
            }
        )
    if soda_type == "denodo":
        return _omit_none(
            {
                "type": "denodo",
                "host": host,
                "port": port,
                "username": username,
                "password": password,
                "database": database,
            }
        )
    if soda_type == "dremio":
        return _omit_none(
            {
                "type": "dremio",
                "host": host,
                "port": port or 9047,
                "username": username,
                "password": password,
                "schema": schema,
            }
        )
    if soda_type == "motherduck":
        return _omit_none(
            {
                "type": "motherduck",
                "token": token,
                "database": database or path,
                "schema": schema,
            }
        )
    if soda_type == "db2":
        return _omit_none(
            {
                "type": "db2",
                "host": host,
                "port": port or 50000,
                "username": username,
                "password": password,
                "database": database,
                "schema": schema,
            }
        )
    if soda_type == "fabric":
        return _omit_none(
            {
                "type": "fabric",
                "tenant_id": conn_params.get("tenant_id"),
                "client_id": conn_params.get("client_id"),
                "client_secret": conn_params.get("client_secret"),
                "workspace": conn_params.get("workspace"),
                "lakehouse": conn_params.get("lakehouse") or database,
            }
        )
    if soda_type == "dask":
        return _omit_none({"type": "dask", "path": path})
    return _omit_none({"type": soda_type, "host": host, "port": port, "database": database})


def build_datasource_config(data_source_name: str, server_type: str, conn_params: dict) -> str:
    soda_type = SODA_TYPE_MAP.get(server_type, server_type)
    safe_name = sanitize_data_source_name(data_source_name)
    body = _build_connection_dict(soda_type, conn_params)
    root = {f"data_source {safe_name}": body}
    return yaml.dump(
        root,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )
