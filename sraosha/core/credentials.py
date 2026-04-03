"""Resolve and inject database credentials from the connections table.

Looks up the connection linked to a contract's server block, decrypts
credentials, and temporarily sets the ``DATACONTRACT_*`` env vars that
``datacontract-cli`` expects.
"""

from __future__ import annotations

import contextlib
import logging
import os
from typing import Any, Generator

logger = logging.getLogger(__name__)


def ordered_connection_names_from_contract_doc(doc: dict) -> list[str]:
    """Names to try in YAML ``servers`` order (explicit map or server key as name)."""
    servers = doc.get("servers") or {}
    if not isinstance(servers, dict) or not servers:
        return []
    xs = doc.get("x-sraosha") or {}
    if not isinstance(xs, dict):
        xs = {}
    sc = xs.get("server_connections") or {}
    if not isinstance(sc, dict):
        sc = {}
    names: list[str] = []
    for sk in servers:
        if sk in sc:
            ref = sc[sk]
            if isinstance(ref, str) and ref.strip():
                names.append(ref.strip())
            elif isinstance(ref, dict):
                n = ref.get("name")
                if n is not None and str(n).strip():
                    names.append(str(n).strip())
            else:
                names.append(sk)
        else:
            names.append(sk)
    return names


ENV_VAR_MAP: dict[str, dict[str, str]] = {
    "postgres": {
        "username": "DATACONTRACT_POSTGRES_USERNAME",
        "password": "DATACONTRACT_POSTGRES_PASSWORD",
    },
    "mysql": {
        "username": "DATACONTRACT_MYSQL_USERNAME",
        "password": "DATACONTRACT_MYSQL_PASSWORD",
    },
    "redshift": {
        "username": "DATACONTRACT_REDSHIFT_USERNAME",
        "password": "DATACONTRACT_REDSHIFT_PASSWORD",
    },
    "snowflake": {
        "username": "DATACONTRACT_SNOWFLAKE_USERNAME",
        "password": "DATACONTRACT_SNOWFLAKE_PASSWORD",
    },
    "trino": {
        "username": "DATACONTRACT_TRINO_USERNAME",
        "password": "DATACONTRACT_TRINO_PASSWORD",
    },
    "bigquery": {
        "service_account_json": "DATACONTRACT_BIGQUERY_ACCOUNT_INFO_JSON",
    },
    "databricks": {
        "token": "DATACONTRACT_DATABRICKS_TOKEN",
    },
}


@contextlib.contextmanager
def inject_credentials(
    server_type: str, credentials: dict[str, Any]
) -> Generator[None, None, None]:
    """Context manager that sets DATACONTRACT_* env vars and cleans up after."""
    mapping = ENV_VAR_MAP.get(server_type, {})
    originals: dict[str, str | None] = {}

    for cred_key, env_var in mapping.items():
        value = credentials.get(cred_key)
        if value:
            originals[env_var] = os.environ.get(env_var)
            os.environ[env_var] = value
            logger.debug("Set %s from connection", env_var)

    try:
        yield
    finally:
        for env_var, original in originals.items():
            if original is None:
                os.environ.pop(env_var, None)
            else:
                os.environ[env_var] = original


def resolve_connection_credentials(contract_id: str) -> tuple[str | None, dict[str, Any]]:
    """Look up connection credentials for a contract's server block (sync, for Celery).

    Returns (server_type, credentials_dict) or (None, {}) if no connection found.
    """
    import yaml as _yaml

    from sraosha.tasks.db import get_sync_connection

    with get_sync_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT raw_yaml FROM contracts WHERE contract_id = %s",
            (contract_id,),
        )
        row = cur.fetchone()
        if not row or not row[0]:
            return None, {}
        try:
            doc = _yaml.safe_load(row[0]) or {}
        except Exception:
            return None, {}

        names = ordered_connection_names_from_contract_doc(doc)
        for nm in names:
            cur.execute(
                """SELECT server_type, username, password_encrypted,
                          token_encrypted, service_account_json_encrypted
                   FROM connections WHERE name = %s LIMIT 1""",
                (nm,),
            )
            crow = cur.fetchone()
            if crow:
                return _parse_sync_cred_row(crow)

        server_types = [
            s.get("type")
            for s in (doc.get("servers") or {}).values()
            if isinstance(s, dict) and s.get("type")
        ]
        if server_types:
            cur.execute(
                """SELECT server_type, username, password_encrypted,
                          token_encrypted, service_account_json_encrypted
                   FROM connections WHERE server_type = %s LIMIT 1""",
                (server_types[0],),
            )
            crow = cur.fetchone()
            if crow:
                return _parse_sync_cred_row(crow)

    return None, {}


def _parse_sync_cred_row(row: tuple) -> tuple[str, dict[str, Any]]:
    from sraosha.crypto import decrypt

    server_type, username, pw_enc, tok_enc, sa_enc = row
    creds: dict[str, Any] = {}
    if username:
        creds["username"] = username
    if pw_enc:
        creds["password"] = decrypt(pw_enc)
    if tok_enc:
        creds["token"] = decrypt(tok_enc)
    if sa_enc:
        creds["service_account_json"] = decrypt(sa_enc)
    return server_type, creds


async def resolve_connection_credentials_async(
    contract_id: str, db,
) -> tuple[str | None, dict[str, Any]]:
    """Look up connection credentials (async, for API).

    Prefers ``x-sraosha.server_connections`` (per server key) when present, then
    matches saved ``Connection`` names to server keys, then ``server_type``.
    """
    from sqlalchemy import select

    from sraosha.models.connection import Connection
    from sraosha.models.contract import Contract

    result = await db.execute(
        select(Contract).where(Contract.contract_id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        return None, {}

    import yaml

    try:
        doc = yaml.safe_load(contract.raw_yaml) or {}
    except Exception:
        return None, {}

    servers = doc.get("servers", {})
    if not servers:
        return None, {}

    names = ordered_connection_names_from_contract_doc(doc)
    for nm in names:
        res = await db.execute(select(Connection).where(Connection.name == nm))
        conn_obj = res.scalar_one_or_none()
        if conn_obj:
            return _extract_creds(conn_obj)

    server_types = [
        s.get("type") for s in servers.values() if isinstance(s, dict) and s.get("type")
    ]
    if server_types:
        res = await db.execute(
            select(Connection).where(Connection.server_type == server_types[0]).limit(1)
        )
        conn_obj = res.scalar_one_or_none()
        if conn_obj:
            return _extract_creds(conn_obj)

    return None, {}


def _extract_creds(conn_obj) -> tuple[str, dict[str, Any]]:
    from sraosha.crypto import decrypt

    creds: dict[str, Any] = {}
    if conn_obj.username:
        creds["username"] = conn_obj.username
    if conn_obj.password_encrypted:
        creds["password"] = decrypt(conn_obj.password_encrypted)
    if conn_obj.token_encrypted:
        creds["token"] = decrypt(conn_obj.token_encrypted)
    if conn_obj.service_account_json_encrypted:
        creds["service_account_json"] = decrypt(conn_obj.service_account_json_encrypted)
    return conn_obj.server_type, creds
