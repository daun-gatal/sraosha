"""Validation and DQ schedule helpers shared by API and dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import cast

PRESET_SECONDS: dict[str, int] = {
    "hourly": 3600,
    "every_6h": 21600,
    "every_12h": 43200,
    "daily": 86400,
    "weekly": 604800,
}


def compute_next_schedule_run(preset: str, cron_expr: str | None) -> datetime:
    """Compute next run time from interval preset or cron expression."""
    now = datetime.now(timezone.utc)
    if preset == "custom" and cron_expr:
        from croniter import croniter

        cron = croniter(cron_expr, now)
        next_run = cast(datetime, cron.get_next(datetime))
        return next_run.replace(tzinfo=timezone.utc)
    seconds = PRESET_SECONDS.get(preset, 86400)
    return now + timedelta(seconds=seconds)
