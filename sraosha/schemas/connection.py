import uuid
from datetime import datetime

from pydantic import BaseModel


class ConnectionCreate(BaseModel):
    name: str
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


class ConnectionUpdate(ConnectionCreate):
    pass


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
    has_password: bool = False
    has_token: bool = False
    has_service_account_json: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConnectionListResponse(BaseModel):
    items: list[ConnectionResponse]
    total: int
