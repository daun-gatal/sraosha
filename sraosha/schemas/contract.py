import uuid
from datetime import datetime

from pydantic import BaseModel


class ContractCreateRequest(BaseModel):
    contract_id: str
    title: str
    description: str | None = None
    file_path: str
    owner_team: str | None = None
    raw_yaml: str
    enforcement_mode: str = "block"


class ContractUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    file_path: str | None = None
    owner_team: str | None = None
    raw_yaml: str | None = None
    enforcement_mode: str | None = None
    is_active: bool | None = None


class ContractResponse(BaseModel):
    id: uuid.UUID
    contract_id: str
    title: str
    description: str | None
    file_path: str
    owner_team: str | None
    enforcement_mode: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContractDetailResponse(ContractResponse):
    raw_yaml: str


class ContractListResponse(BaseModel):
    items: list[ContractResponse]
    total: int
