import logging
from dataclasses import dataclass

from sraosha.drift.baseline import BaselineStats
from sraosha.drift.metrics import MetricDefinition, MetricValue

logger = logging.getLogger(__name__)


@dataclass
class DriftAlert:
    metric_type: str
    table: str
    column: str | None
    current_value: float
    warning_threshold: float | None
    breach_threshold: float | None
    is_warning: bool
    is_breached: bool
    trend_slope: float | None
    estimated_breach_in_runs: int | None


class DriftAlerter:
    """Compares measured metric values against thresholds and baselines."""

    def check(
        self,
        value: MetricValue,
        definition: MetricDefinition,
        baseline: BaselineStats | None = None,
    ) -> DriftAlert | None:
        is_warning = False
        is_breached = False

        if definition.warning_threshold is not None and value.value >= definition.warning_threshold:
            is_warning = True

        if definition.breach_threshold is not None and value.value >= definition.breach_threshold:
            is_breached = True

        trending_to_breach = baseline.is_trending_to_breach if baseline else False

        if not is_warning and not is_breached and not trending_to_breach:
            return None

        return DriftAlert(
            metric_type=value.metric_type.value,
            table=value.table,
            column=value.column,
            current_value=value.value,
            warning_threshold=definition.warning_threshold,
            breach_threshold=definition.breach_threshold,
            is_warning=is_warning,
            is_breached=is_breached,
            trend_slope=baseline.trend_slope if baseline else None,
            estimated_breach_in_runs=baseline.estimated_breach_in_runs if baseline else None,
        )
