from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DQCheckCreate(BaseModel):
    name: str
    description: str | None = None
    connection_id: uuid.UUID
    team_id: uuid.UUID | None = None
    alerting_profile_id: uuid.UUID | None = None
    data_source_name: str
    sodacl_yaml: str
    tables: list[str] = Field(default_factory=list)
    check_categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class DQCheckUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    connection_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    alerting_profile_id: uuid.UUID | None = None
    data_source_name: str | None = None
    sodacl_yaml: str | None = None
    tables: list[str] | None = None
    check_categories: list[str] | None = None
    tags: list[str] | None = None
    is_enabled: bool | None = None


class DQCheckResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    connection_id: uuid.UUID
    team_id: uuid.UUID | None
    alerting_profile_id: uuid.UUID | None
    owner_team: str | None
    data_source_name: str
    sodacl_yaml: str
    tables: list[str]
    check_categories: list[str]
    is_enabled: bool
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    latest_status: str | None = None
    pass_rate: float | None = None
    run_count: int = 0

    model_config = {"from_attributes": True}


class DQCheckListResponse(BaseModel):
    items: list[DQCheckResponse]
    total: int


class DQRunResponse(BaseModel):
    id: uuid.UUID
    dq_check_id: uuid.UUID
    status: str
    checks_total: int
    checks_passed: int
    checks_warned: int
    checks_failed: int
    results_json: dict | None
    diagnostics_json: dict | None
    run_log: str | None
    duration_ms: int | None
    triggered_by: str
    run_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("results_json", "diagnostics_json", mode="before")
    @classmethod
    def _normalize_json_payload(cls, v: Any) -> Any:
        """DB / Soda may store [] or other JSON; API exposes dict | None."""
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, list):
            return None if len(v) == 0 else {"items": v}
        return None


class DQRunListResponse(BaseModel):
    items: list[DQRunResponse]
    total: int


class DQRunListItem(DQRunResponse):
    """DQ run row for global feeds (includes check display name)."""

    dq_check_name: str


class DQRunGlobalListResponse(BaseModel):
    items: list[DQRunListItem]
    total: int


class DQSummaryResponse(BaseModel):
    total_checks: int
    healthy: int
    warning: int
    failed: int
    error: int
    overall_pass_rate: float | None


class DQCheckTemplateItem(BaseModel):
    key: str
    label: str
    description: str
    category: str
    needs_column: bool
    column_types: list[str]
    params: list[dict[str, Any]]
    icon: str = ""
    soda_section: int = 0


class DQCheckTemplateListResponse(BaseModel):
    items: list[DQCheckTemplateItem]


class DQPreviewSodaCLRequest(BaseModel):
    template_key: str
    table: str
    column: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class DQPreviewSodaCLResponse(BaseModel):
    sodacl_yaml: str


class DQScheduleResponse(BaseModel):
    id: uuid.UUID
    dq_check_id: uuid.UUID
    is_enabled: bool
    interval_preset: str
    cron_expression: str | None
    next_run_at: datetime
    last_run_at: datetime | None

    model_config = {"from_attributes": True}
