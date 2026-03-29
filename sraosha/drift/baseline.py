import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BaselineStats:
    mean: float
    std_dev: float
    trend_slope: float
    is_trending_to_breach: bool
    estimated_breach_in_runs: int | None


class BaselineComputer:
    """
    Computes statistical baselines from the last N metric values.
    trend_slope via linear regression on the last N values.
    """

    def __init__(self, window_size: int = 14):
        self.window_size = window_size

    def compute(
        self, values: list[float], breach_threshold: float | None = None
    ) -> BaselineStats:
        if not values:
            return BaselineStats(
                mean=0.0,
                std_dev=0.0,
                trend_slope=0.0,
                is_trending_to_breach=False,
                estimated_breach_in_runs=None,
            )

        recent = values[-self.window_size :]
        arr = np.array(recent, dtype=float)

        mean = float(np.mean(arr))
        std_dev = float(np.std(arr))

        if len(arr) >= 2:
            x = np.arange(len(arr), dtype=float)
            slope, _ = np.polyfit(x, arr, 1)
            trend_slope = float(slope)
        else:
            trend_slope = 0.0

        is_trending = False
        estimated_breach: int | None = None

        if breach_threshold is not None and trend_slope > 0:
            current = float(arr[-1])
            if current < breach_threshold:
                remaining = breach_threshold - current
                estimated_breach = max(1, int(remaining / trend_slope))
                is_trending = True
            elif current >= breach_threshold:
                is_trending = True
                estimated_breach = 0

        return BaselineStats(
            mean=mean,
            std_dev=std_dev,
            trend_slope=trend_slope,
            is_trending_to_breach=is_trending,
            estimated_breach_in_runs=estimated_breach,
        )

    def compute_for_contract(
        self,
        metrics_history: dict[str, list[float]],
        thresholds: dict[str, float | None] | None = None,
    ) -> dict[str, BaselineStats]:
        """
        metrics_history: dict keyed by "{table}.{column}.{metric_type}" with list of values.
        thresholds: same keys mapping to breach_threshold.
        """
        results: dict[str, BaselineStats] = {}
        thresholds = thresholds or {}

        for key, values in metrics_history.items():
            breach = thresholds.get(key)
            results[key] = self.compute(values, breach_threshold=breach)

        return results
