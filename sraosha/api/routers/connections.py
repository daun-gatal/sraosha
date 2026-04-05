import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from sraosha.api.deps import get_db
from sraosha.api.introspect import map_sql_type_to_contract_field
from sraosha.core.connection_server_types import SUPPORTED_CONNECTION_SERVER_TYPES
from sraosha.crypto import encrypt
from sraosha.models.connection import Connection
from sraosha.models.dq_check import DQCheck
from sraosha.schemas.connection import (
    ConnectionCreate,
    ConnectionListResponse,
    ConnectionResponse,
    ConnectionTestRequest,
    ConnectionTestResponse,
    ConnectionUpdate,
)
from sraosha.schemas.introspection import (
    ColumnItem,
    ColumnListResponse,
    TableItem,
    TableListResponse,
)
from sraosha.services.connection_introspect import list_columns_sync, list_tables_sync
from sraosha.services.connection_test import params_for_connection_test, verify_connection_params

router = APIRouter()
logger = logging.getLogger(__name__)

# Path segments cannot be empty; frontend sends this when schema is "" (e.g. MySQL default).
_EMPTY_SCHEMA_PATH_TOKEN = "__sraosha_empty__"


def _decode_schema_path_segment(value: str) -> str:
    if value == _EMPTY_SCHEMA_PATH_TOKEN:
        return ""
    return value


def _normalize_server_type(server_type: str) -> str:
    s = (server_type or "").strip().lower()
    if not s:
        raise ValueError("server_type is required")
    if s == "postgresql":
        return "postgres"
    # Legacy alias: Cloud SQL Postgres was stored as cloudsql; Soda YAML is postgres.
    if s == "cloudsql":
        return "postgres"
    if s == "sqlserver":
        return "mssql"
    return s


def _require_supported_server_type(st: str) -> None:
    if st not in SUPPORTED_CONNECTION_SERVER_TYPES:
        allowed = ", ".join(SUPPORTED_CONNECTION_SERVER_TYPES)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported server_type {st!r}. Currently supported: {allowed}.",
        )


def _connection_to_response(c: Connection) -> ConnectionResponse:
    return ConnectionResponse(
        id=c.id,
        name=c.name,
        server_type=c.server_type,
        description=c.description,
        host=c.host,
        port=c.port,
        database=c.database,
        schema_name=c.schema_name,
        account=c.account,
        warehouse=c.warehouse,
        role=c.role,
        catalog=c.catalog,
        http_path=c.http_path,
        project=c.project,
        dataset=c.dataset,
        location=c.location,
        path=c.path,
        username=c.username,
        extra_params=c.extra_params if c.extra_params else None,
        has_password=c.password_encrypted is not None,
        has_token=c.token_encrypted is not None,
        has_service_account_json=c.service_account_json_encrypted is not None,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("", response_model=ConnectionListResponse)
async def list_connections(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Connection).order_by(Connection.name))
    rows = result.scalars().all()
    items = [_connection_to_response(c) for c in rows]
    return ConnectionListResponse(items=items, total=len(items))


@router.post("/test", response_model=ConnectionTestResponse)
async def test_connection_api(body: ConnectionTestRequest, db: AsyncSession = Depends(get_db)):
    try:
        st = _normalize_server_type(body.server_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _require_supported_server_type(st)
    row: Connection | None = None
    if body.existing_connection_id is not None:
        row = await db.get(Connection, body.existing_connection_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Connection not found")
    params = params_for_connection_test(body, row)
    ok, msg = await asyncio.to_thread(verify_connection_params, st, params)
    return ConnectionTestResponse(ok=ok, message=msg)


@router.post("", response_model=ConnectionResponse, status_code=201)
async def create_connection(body: ConnectionCreate, db: AsyncSession = Depends(get_db)):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    try:
        st = _normalize_server_type(body.server_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _require_supported_server_type(st)
    row = Connection(
        name=name,
        server_type=st,
        description=body.description,
        host=body.host,
        port=body.port,
        database=body.database,
        schema_name=body.schema_name,
        account=body.account,
        warehouse=body.warehouse,
        role=body.role,
        catalog=body.catalog,
        http_path=body.http_path,
        project=body.project,
        dataset=body.dataset,
        location=body.location,
        path=body.path,
        username=body.username,
        password_encrypted=(
            encrypt(body.password) if body.password and body.password.strip() else None
        ),
        token_encrypted=(
            encrypt(body.token) if body.token and body.token.strip() else None
        ),
        service_account_json_encrypted=(
            encrypt(body.service_account_json)
            if body.service_account_json and body.service_account_json.strip()
            else None
        ),
        extra_params=dict(body.extra_params) if body.extra_params else {},
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Connection name already exists") from None
    await db.refresh(row)
    return _connection_to_response(row)


@router.get("/{connection_id}/tables", response_model=TableListResponse)
async def connection_tables(
    connection_id: str,
    schema: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        uid = uuid.UUID(connection_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid connection ID") from None
    result = await db.execute(select(Connection).where(Connection.id == uid))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Connection not found")
    try:
        schema_used, rows = await asyncio.to_thread(list_tables_sync, c, schema)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        logger.warning("connection tables introspection: %s", exc)
        raise HTTPException(
            status_code=502, detail=f"Could not connect to database: {exc!s}"
        ) from exc
    except Exception as exc:
        logger.exception("connection tables introspection failed")
        raise HTTPException(
            status_code=502, detail=f"Introspection failed: {exc!s}"
        ) from exc
    items = [
        TableItem(name=r["table_name"], kind=r["table_type"]) for r in rows
    ]
    return TableListResponse(items=items, schema_name=schema_used)


@router.get("/{connection_id}/tables/{schema}/{table}/columns", response_model=ColumnListResponse)
async def connection_table_columns(
    connection_id: str,
    schema: str,
    table: str,
    db: AsyncSession = Depends(get_db),
):
    schema = _decode_schema_path_segment(schema)
    try:
        uid = uuid.UUID(connection_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid connection ID") from None
    result = await db.execute(select(Connection).where(Connection.id == uid))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Connection not found")
    try:
        schema_used, cols = await asyncio.to_thread(list_columns_sync, c, schema, table)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        logger.warning("connection columns introspection: %s", exc)
        raise HTTPException(
            status_code=502, detail=f"Could not connect to database: {exc!s}"
        ) from exc
    except Exception as exc:
        logger.exception("connection columns introspection failed")
        raise HTTPException(
            status_code=502, detail=f"Introspection failed: {exc!s}"
        ) from exc
    items = [
        ColumnItem(
            name=col["column_name"],
            data_type=col["data_type"],
            is_nullable=col["is_nullable"],
            ordinal_position=col["ordinal_position"],
            suggested_field_type=map_sql_type_to_contract_field(col["data_type"]),
        )
        for col in cols
    ]
    return ColumnListResponse(
        items=items, schema_name=schema_used, table_name=table
    )


@router.patch("/{connection_id}", response_model=ConnectionResponse)
async def update_connection(
    connection_id: str,
    body: ConnectionUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        uid = uuid.UUID(connection_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid connection ID") from None
    c = await db.get(Connection, uid)
    if not c:
        raise HTTPException(status_code=404, detail="Connection not found")
    data = body.model_dump(exclude_unset=True)
    secret_map = (
        ("password", "password_encrypted"),
        ("token", "token_encrypted"),
        ("service_account_json", "service_account_json_encrypted"),
    )
    for key, col in secret_map:
        if key not in data:
            continue
        val = data.pop(key)
        if val is not None and str(val).strip():
            setattr(c, col, encrypt(str(val)))
    if "name" in data:
        n = (data.pop("name") or "").strip()
        if not n:
            raise HTTPException(status_code=400, detail="name cannot be empty")
        c.name = n
    if "server_type" in data:
        try:
            st = _normalize_server_type(data.pop("server_type") or "")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _require_supported_server_type(st)
        c.server_type = st
    scalar_keys = (
        "description",
        "host",
        "port",
        "database",
        "schema_name",
        "account",
        "warehouse",
        "role",
        "catalog",
        "http_path",
        "project",
        "dataset",
        "location",
        "path",
        "username",
    )
    for k in scalar_keys:
        if k in data:
            setattr(c, k, data.pop(k))
    if "extra_params" in data:
        ep = data.pop("extra_params")
        c.extra_params = dict(ep) if ep is not None else {}
    if data:
        raise HTTPException(status_code=400, detail=f"Unexpected fields: {', '.join(data)}")
    c.updated_at = datetime.now(timezone.utc)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Connection name already exists") from None
    await db.refresh(c)
    return _connection_to_response(c)


@router.delete("/{connection_id}", status_code=204)
async def delete_connection(connection_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uid = uuid.UUID(connection_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid connection ID") from None
    c = await db.get(Connection, uid)
    if not c:
        raise HTTPException(status_code=404, detail="Connection not found")
    n = await db.scalar(
        select(func.count()).select_from(DQCheck).where(DQCheck.connection_id == uid)
    )
    if (n or 0) > 0:
        raise HTTPException(
            status_code=409,
            detail="Connection is referenced by one or more data quality checks",
        )
    await db.delete(c)


@router.get("/{connection_id}", response_model=ConnectionResponse)
async def get_connection(connection_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uid = uuid.UUID(connection_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid connection ID") from None
    result = await db.execute(select(Connection).where(Connection.id == uid))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Connection not found")
    return _connection_to_response(c)
