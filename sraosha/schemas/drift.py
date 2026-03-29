import uuid
from datetime import datetime

from pydantic import BaseModel


class DriftMetricResponse(BaseModel):
    id: uuid.UUID
    contract_id: str
    metric_type: str
    table_name: str
    column_name: str | None
    value: float
    warning_threshold: float | None
    breach_threshold: float | None
    is_warning: bool
    is_breached: bool
    measured_at: datetime

    model_config = {"from_attributes": True}


class DriftHistoryResponse(BaseModel):
    items: list[DriftMetricResponse]


class DriftBaselineResponse(BaseModel):
    id: uuid.UUID
    contract_id: str
    metric_type: str
    table_name: str
    column_name: str | None
    mean: float | None
    std_dev: float | None
    trend_slope: float | None
    is_trending_to_breach: bool
    estimated_breach_in_runs: int | None
    window_size: int
    computed_at: datetime

    model_config = {"from_attributes": True}


class DriftAlertResponse(BaseModel):
    contract_id: str
    metric_type: str
    table_name: str
    column_name: str | None
    current_value: float
    warning_threshold: float | None
    breach_threshold: float | None
    trend_slope: float | None
    estimated_breach_in_runs: int | None
