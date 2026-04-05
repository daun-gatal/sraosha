import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ContractColumnPreview(BaseModel):
    """One model field line for guided contract preview."""

    name: str
    required: bool = False
    unique: bool = False
    field_type: str | None = Field(
        default=None,
        description="Data contract field type; if omitted, client may infer from SQL.",
    )


class ContractPreviewRequest(BaseModel):
    """Build datacontract YAML from a single table + columns (no raw YAML editing)."""

    connection_id: uuid.UUID
    contract_id: str
    title: str
    table_name: str
    columns: list[ContractColumnPreview]
    server_key: str = "production"
    schema_name: str | None = Field(
        default=None,
        description="Database schema (e.g. public). Defaults from connection.",
    )
    description: str | None = None
    spec_version: str = "1.1.0"
    version: str = "1.0.0"
    owner: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    team_id: uuid.UUID | None = None
    alerting_profile_id: uuid.UUID | None = None
    enforcement_mode: str = "block"


class ContractPreviewResponse(BaseModel):
    raw_yaml: str


class ContractCreateRequest(BaseModel):
    contract_id: str
    title: str
    description: str | None = None
    file_path: str | None = None
    team_id: uuid.UUID | None = None
    alerting_profile_id: uuid.UUID | None = None
    raw_yaml: str
    enforcement_mode: str = "block"


class ContractUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    file_path: str | None = None
    team_id: uuid.UUID | None = None
    alerting_profile_id: uuid.UUID | None = None
    raw_yaml: str | None = None
    enforcement_mode: str | None = None
    is_active: bool | None = None
    spec_version: str | None = Field(
        default=None,
        description="If set, updates dataContractSpecification in raw_yaml after save.",
    )
    info_version: str | None = Field(
        default=None,
        description="If set, updates info.version in raw_yaml after save.",
    )


class ContractResponse(BaseModel):
    id: uuid.UUID
    contract_id: str
    title: str
    description: str | None
    file_path: str
    team_id: uuid.UUID | None
    alerting_profile_id: uuid.UUID | None
    owner_team: str | None
    enforcement_mode: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContractDetailResponse(ContractResponse):
    raw_yaml: str
    spec_version: str | None = Field(
        default=None,
        description="dataContractSpecification from raw_yaml (for guided form).",
    )
    info_version: str | None = Field(
        default=None,
        description="info.version from raw_yaml (for guided form).",
    )


class ContractListResponse(BaseModel):
    items: list[ContractResponse]
    total: int
