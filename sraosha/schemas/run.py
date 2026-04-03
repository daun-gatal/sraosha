import uuid
from datetime import datetime

from pydantic import BaseModel


class RunRequest(BaseModel):
    server: str | None = None
    enforcement_mode: str | None = None


class ValidationRunResponse(BaseModel):
    id: uuid.UUID
    contract_id: str
    status: str
    enforcement_mode: str
    checks_total: int
    checks_passed: int
    checks_failed: int
    failures: list[dict] | None
    server: str | None
    triggered_by: str | None
    duration_ms: int | None
    error_message: str | None
    run_log: str | None = None
    run_at: datetime

    model_config = {"from_attributes": True}


class RunListResponse(BaseModel):
    items: list[ValidationRunResponse]
    total: int


class RunSummaryItem(BaseModel):
    contract_id: str
    total_runs: int
    passed: int
    failed: int
    error: int


class RunSummaryResponse(BaseModel):
    items: list[RunSummaryItem]
