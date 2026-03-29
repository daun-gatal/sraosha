from dataclasses import dataclass
from enum import Enum


class MetricType(str, Enum):
    NULL_RATE = "null_rate"
    ROW_COUNT = "row_count"
    ROW_COUNT_DELTA = "row_count_delta"
    TYPE_MISMATCH = "type_mismatch"
    DUPLICATE_RATE = "duplicate_rate"
    VALUE_DIST = "value_dist"


@dataclass
class MetricDefinition:
    metric_type: MetricType
    table: str
    column: str | None
    warning_threshold: float | None
    breach_threshold: float | None


@dataclass
class MetricValue:
    metric_type: MetricType
    table: str
    column: str | None
    value: float
    run_id: str
    measured_at: str
