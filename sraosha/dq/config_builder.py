from __future__ import annotations

import re
from typing import Any, cast

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
    # Soda documents ClickHouse via MySQL wire protocol (soda-mysql).
    "clickhouse": "mysql",
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
    "dask": "dask",
    "postgresql": "postgres",
}

SODA_CONNECTOR_TYPES: frozenset[str] = frozenset(SODA_TYPE_MAP.values())

# Connection row / first-class API fields merged into scan params; not passed through to YAML again.
_INTERNAL_CONN_PARAM_KEYS: frozenset[str] = frozenset(
    {
        "host",
        "port",
        "database",
        "schema",
        "username",
        "password",
        "account",
        "warehouse",
        "role",
        "catalog",
        "httpPath",
        "project",
        "dataset",
        "path",
        "location",
        "token",
        "service_account_json",
        "region",
        "s3_staging_dir",
        "tenant_id",
        "client_id",
        "client_secret",
        "workspace",
        "lakehouse",
    }
)

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


def resolve_data_source_name(server_type: str, explicit: str | None) -> tuple[str, str | None]:
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


def _merge_soda_passthrough(body: dict[str, Any], conn_params: dict[str, Any]) -> None:
    """Merge Soda-only keys from connection ``extra_params`` (flattened into conn_params).

    Non-internal keys override built-in YAML (e.g. ``charset`` / ``use_unicode`` for MySQL).
    """
    for k, v in conn_params.items():
        if k in _INTERNAL_CONN_PARAM_KEYS or v is None:
            continue
        body[k] = v


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
        # mysql-connector-python defaults to charset "utf8", which many servers/drivers reject;
        # utf8mb4 is the supported full Unicode charset for MySQL 5.5.3+.
        return _omit_none(
            {
                "type": "mysql",
                "host": host,
                "port": port or 3306,
                "username": username,
                "password": password,
                "database": database,
                "charset": "utf8mb4",
                "use_unicode": True,
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
                "schema": schema,
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
    if soda_type == "oracle":
        o: dict[str, Any] = {"type": "oracle", "username": username, "password": password}
        cs = conn_params.get("connectstring")
        if cs:
            o["connectstring"] = cs
        else:
            o["host"] = host
            o["port"] = port or 1521
            sn = conn_params.get("service_name")
            if sn:
                o["service_name"] = sn
            elif database:
                o["service_name"] = database
        return _omit_none(o)
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
        dbn = (database or path or "").strip() or "md"
        tok = (token or "").strip()
        md_uri = f"md:{dbn}?motherduck_token={tok}" if tok else dbn
        read_only = conn_params.get("read_only")
        if read_only is None:
            read_only = True
        return _omit_none(
            {
                "type": "duckdb",
                "database": md_uri,
                "read_only": read_only,
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
    _merge_soda_passthrough(body, conn_params)
    root = {f"data_source {safe_name}": body}
    return cast(
        str,
        yaml.dump(
            root,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=120,
        ),
    )
