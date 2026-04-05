from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ScheduleRequest(BaseModel):
    interval_preset: str = "daily"
    cron_expression: str | None = None
    is_enabled: bool = True


class ScheduleResponse(BaseModel):
    id: uuid.UUID
    contract_id: str
    is_enabled: bool
    interval_preset: str
    cron_expression: str | None
    next_run_at: datetime
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScheduleListItem(BaseModel):
    id: uuid.UUID
    schedule_type: str = "contract"
    contract_id: str | None = None
    contract_title: str | None = None
    dq_check_id: uuid.UUID | None = None
    dq_check_name: str | None = None
    owner_team: str | None = None
    is_enabled: bool
    interval_preset: str
    cron_expression: str | None = None
    next_run_at: datetime
    last_run_at: datetime | None = None
    last_run_id: uuid.UUID | None = None


class ScheduleListResponse(BaseModel):
    items: list[ScheduleListItem]
    total: int
