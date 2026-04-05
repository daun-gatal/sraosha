"""Test database connectivity using the same drivers as scans (no persisted connection row)."""

from __future__ import annotations

import json
import logging
from typing import Any

from sraosha.crypto import decrypt
from sraosha.models.connection import Connection
from sraosha.schemas.connection import ConnectionTestRequest

logger = logging.getLogger(__name__)


def connection_model_to_params(c: Connection) -> dict[str, Any]:
    """Flatten Connection row + decrypted secrets + extra_params (same shape as dq_scan)."""
    params: dict[str, Any] = {
        "host": c.host,
        "port": c.port,
        "database": c.database,
        "schema": c.schema_name,
        "username": c.username,
        "account": c.account,
        "warehouse": c.warehouse,
        "role": c.role,
        "catalog": c.catalog,
        "httpPath": c.http_path,
        "project": c.project,
        "dataset": c.dataset,
        "path": c.path,
        "location": c.location,
    }
    if c.password_encrypted:
        params["password"] = decrypt(c.password_encrypted)
    if c.token_encrypted:
        params["token"] = decrypt(c.token_encrypted)
    if c.service_account_json_encrypted:
        params["service_account_json"] = decrypt(c.service_account_json_encrypted)
    if c.extra_params and isinstance(c.extra_params, dict):
        params.update(c.extra_params)
    return {k: v for k, v in params.items() if v is not None}


def _port(params: dict[str, Any], default: int) -> int:
    p = params.get("port")
    if p is None or p == "":
        return default
    return int(p)


def _err(exc: BaseException) -> str:
    s = str(exc).strip() or exc.__class__.__name__
    return s[:800]


def verify_connection_params(server_type: str, params: dict[str, Any]) -> tuple[bool, str | None]:
    """
    Attempt a minimal read-only connectivity check for the given engine.
    Returns (True, None) on success, or (False, error_message).
    """
    st = (server_type or "").strip().lower()
    if st in ("postgresql", "cloudsql"):
        st = "postgres"
    if st == "sqlserver":
        st = "mssql"
    try:
        if st == "postgres":
            return _test_postgres(params, default_port=5432)
        if st == "mysql" or st == "clickhouse":
            return _test_mysql(params)
        if st == "redshift":
            return _test_postgres(params, default_port=5439)
        if st == "snowflake":
            return _test_snowflake(params)
        if st == "bigquery":
            return _test_bigquery(params)
        if st == "mssql":
            return _test_mssql(params)
        if st == "oracle":
            return _test_oracle(params)
        if st == "trino":
            return _test_trino_presto(params, legacy_prepared_statements=False)
        if st == "presto":
            return _test_trino_presto(params, legacy_prepared_statements=True)
        if st == "motherduck":
            return _test_motherduck(params)
    except Exception as exc:
        logger.debug("connection test failed", exc_info=True)
        return False, _err(exc)
    return False, f"Unsupported server_type for test: {server_type!r}"


def _test_postgres(params: dict[str, Any], *, default_port: int) -> tuple[bool, str | None]:
    import psycopg2

    host = (params.get("host") or "localhost").strip()
    port = _port(params, default_port)
    raw_db = params.get("database")
    if default_port == 5439:
        if raw_db is None or str(raw_db).strip() == "":
            return False, "Database name is required for Redshift"
        db = str(raw_db).strip()
    else:
        db = str(raw_db).strip() if raw_db not in (None, "") else "postgres"
    user = (params.get("username") or "postgres").strip()
    password = params.get("password") or ""
    conn = psycopg2.connect(
        host=host, port=port, dbname=db, user=user, password=password, connect_timeout=15
    )
    try:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    finally:
        conn.close()
    return True, None


def _test_mysql(params: dict[str, Any]) -> tuple[bool, str | None]:
    import pymysql

    host = (params.get("host") or "localhost").strip()
    port = _port(params, 3306)
    database = (params.get("database") or "").strip()
    user = (params.get("username") or "root").strip()
    password = params.get("password") or ""
    conn = pymysql.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        charset="utf8mb4",
        connect_timeout=15,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    finally:
        conn.close()
    return True, None


def _test_snowflake(params: dict[str, Any]) -> tuple[bool, str | None]:
    import snowflake.connector

    account = (params.get("account") or "").strip()
    if not account:
        return False, "Snowflake account identifier is required"
    user = (params.get("username") or "").strip()
    password = params.get("password") or ""
    if not user:
        return False, "Username is required"
    kwargs: dict[str, Any] = {
        "user": user,
        "password": password,
        "account": account,
        "login_timeout": 15,
        "network_timeout": 15,
    }
    wh = params.get("warehouse")
    if wh:
        kwargs["warehouse"] = str(wh).strip()
    db = params.get("database")
    if db:
        kwargs["database"] = str(db).strip()
    schema = params.get("schema")
    if schema:
        kwargs["schema"] = str(schema).strip()
    role = params.get("role")
    if role:
        kwargs["role"] = str(role).strip()
    conn = snowflake.connector.connect(**kwargs)
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
    finally:
        conn.close()
    return True, None


def _test_bigquery(params: dict[str, Any]) -> tuple[bool, str | None]:
    from google.cloud import bigquery
    from google.oauth2 import service_account

    project = (params.get("project") or "").strip()
    if not project:
        return False, "BigQuery project_id is required"
    sa_raw = params.get("service_account_json")
    if sa_raw and str(sa_raw).strip():
        info = json.loads(sa_raw) if isinstance(sa_raw, str) else sa_raw
        creds = service_account.Credentials.from_service_account_info(info)
        client = bigquery.Client(project=project, credentials=creds)
    else:
        client = bigquery.Client(project=project)
    loc = params.get("location")
    loc_s = str(loc).strip() if loc not in (None, "") else None
    job = client.query("SELECT 1", location=loc_s)
    list(job.result())
    return True, None


def _test_mssql(params: dict[str, Any]) -> tuple[bool, str | None]:
    import pyodbc

    host = (params.get("host") or "localhost").strip()
    port = _port(params, 1433)
    database = (params.get("database") or "master").strip()
    user = (params.get("username") or "").strip()
    password = params.get("password") or ""
    if not user:
        return False, "Username is required for SQL Server"
    drivers = (
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "FreeTDS",
    )
    last: BaseException | None = None
    for drv in drivers:
        try:
            conn_str = (
                f"DRIVER={{{drv}}};SERVER={host},{port};DATABASE={database};"
                f"UID={user};PWD={password};Encrypt=yes;TrustServerCertificate=yes;"
            )
            conn = pyodbc.connect(conn_str, timeout=15)
            try:
                cur = conn.cursor()
                cur.execute("SELECT 1")
            finally:
                conn.close()
            return True, None
        except Exception as exc:
            last = exc
    return False, _err(last) if last else "ODBC connection failed"


def _test_oracle(params: dict[str, Any]) -> tuple[bool, str | None]:
    import oracledb

    user = (params.get("username") or "").strip()
    password = params.get("password") or ""
    if not user:
        return False, "Username is required for Oracle"
    cs = (params.get("connectstring") or "").strip()
    if cs:
        conn = oracledb.connect(user=user, password=password, dsn=cs)
    else:
        host = (params.get("host") or "").strip()
        if not host:
            return False, "Host or connectstring (in extra params) is required for Oracle"
        port = _port(params, 1521)
        sn = (params.get("service_name") or params.get("database") or "").strip()
        if not sn:
            return False, "Oracle needs service_name or database (or connectstring in extra params)"
        dsn = oracledb.makedsn(host, port, service_name=sn)
        conn = oracledb.connect(user=user, password=password, dsn=dsn)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM DUAL")
    finally:
        conn.close()
    return True, None


def _test_trino_presto(
    params: dict[str, Any], *, legacy_prepared_statements: bool
) -> tuple[bool, str | None]:
    import trino.auth
    import trino.dbapi as trino

    host = (params.get("host") or "localhost").strip()
    port = _port(params, 8080)
    user = (params.get("username") or "test").strip()
    password = params.get("password") or ""
    catalog = (params.get("catalog") or "hive").strip()
    schema = (params.get("schema") or "default").strip()
    verify = params.get("verify")
    if verify is None:
        verify = True
    http_scheme = params.get("http_scheme")
    if isinstance(http_scheme, str) and http_scheme.strip():
        hs = http_scheme.strip().lower()
    elif port == 443:
        hs = "https"
    else:
        hs = "http"
    auth = (
        trino.auth.BasicAuthentication(user, password)
        if (password and str(password).strip())
        else trino.constants.DEFAULT_AUTH
    )
    conn = trino.connect(
        host=host,
        port=port,
        user=user,
        catalog=catalog,
        schema=schema,
        http_scheme=hs,
        auth=auth,
        verify=bool(verify),
        legacy_prepared_statements=legacy_prepared_statements,
        request_timeout=30,
    )
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
    finally:
        conn.close()
    return True, None


def _test_motherduck(params: dict[str, Any]) -> tuple[bool, str | None]:
    import duckdb

    tok = (params.get("token") or "").strip()
    if not tok:
        return False, "MotherDuck token is required"
    dbn = (params.get("database") or params.get("path") or "md").strip() or "md"
    read_only = params.get("read_only")
    if read_only is None:
        read_only = True
    uri = f"md:{dbn}?motherduck_token={tok}"
    conn = duckdb.connect(uri, read_only=bool(read_only))
    try:
        conn.execute("SELECT 1")
    finally:
        conn.close()
    return True, None


def params_for_connection_test(body: ConnectionTestRequest, c: Connection | None) -> dict[str, Any]:
    """Build flat scan-style params from the test form; merge stored secrets when editing."""
    d = body.model_dump()
    p: dict[str, Any] = {
        "host": d["host"],
        "port": d["port"],
        "database": d["database"],
        "schema": d["schema_name"],
        "username": d["username"],
        "account": d["account"],
        "warehouse": d["warehouse"],
        "role": d["role"],
        "catalog": d["catalog"],
        "httpPath": d["http_path"],
        "project": d["project"],
        "dataset": d["dataset"],
        "path": d["path"],
        "location": d["location"],
    }
    pw = d.get("password")
    if pw and str(pw).strip():
        p["password"] = pw
    elif c is not None and c.password_encrypted:
        p["password"] = decrypt(c.password_encrypted)

    tok = d.get("token")
    if tok and str(tok).strip():
        p["token"] = tok
    elif c is not None and c.token_encrypted:
        p["token"] = decrypt(c.token_encrypted)

    sa = d.get("service_account_json")
    if sa and str(sa).strip():
        p["service_account_json"] = sa
    elif c is not None and c.service_account_json_encrypted:
        p["service_account_json"] = decrypt(c.service_account_json_encrypted)

    ep = d.get("extra_params")
    if body.existing_connection_id is not None and c is not None:
        if ep is not None:
            p.update(ep)
    elif ep is not None:
        p.update(ep)

    return {k: v for k, v in p.items() if v is not None}
