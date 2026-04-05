import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ConnectionFieldsBase(BaseModel):
    """Shared connection form fields (name supplied by subclasses)."""

    server_type: str
    description: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    schema_name: str | None = None
    account: str | None = None
    warehouse: str | None = None
    role: str | None = None
    catalog: str | None = None
    http_path: str | None = None
    project: str | None = None
    dataset: str | None = None
    location: str | None = None
    path: str | None = None
    username: str | None = None
    password: str | None = None
    token: str | None = None
    service_account_json: str | None = None
    extra_params: dict[str, Any] | None = None


class ConnectionCreate(ConnectionFieldsBase):
    name: str


class ConnectionUpdate(BaseModel):
    """Partial update; omit fields to leave unchanged. Non-empty secret fields rotate storage."""

    name: str | None = None
    server_type: str | None = None
    description: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    schema_name: str | None = None
    account: str | None = None
    warehouse: str | None = None
    role: str | None = None
    catalog: str | None = None
    http_path: str | None = None
    project: str | None = None
    dataset: str | None = None
    location: str | None = None
    path: str | None = None
    username: str | None = None
    password: str | None = None
    token: str | None = None
    service_account_json: str | None = None
    extra_params: dict[str, Any] | None = None


class ConnectionResponse(BaseModel):
    id: uuid.UUID
    name: str
    server_type: str
    description: str | None
    host: str | None
    port: int | None
    database: str | None
    schema_name: str | None
    account: str | None
    warehouse: str | None
    role: str | None
    catalog: str | None
    http_path: str | None
    project: str | None
    dataset: str | None
    location: str | None
    path: str | None
    username: str | None
    extra_params: dict[str, Any] | None = None
    has_password: bool = False
    has_token: bool = False
    has_service_account_json: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConnectionListResponse(BaseModel):
    items: list[ConnectionResponse]
    total: int


class ConnectionTestRequest(ConnectionFieldsBase):
    """Create-shaped body; name optional. Use existing_connection_id to merge DB secrets (edit)."""

    name: str | None = None
    existing_connection_id: uuid.UUID | None = None


class ConnectionTestResponse(BaseModel):
    ok: bool
    message: str | None = None
