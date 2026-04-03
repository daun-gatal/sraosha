"""Pure helpers for compliance score computation (Celery + dashboard)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def rolling_30d_window(now: datetime | None = None) -> tuple[datetime, datetime, date, date]:
    """Return cutoff/now for SQL filters and period dates for compliance_scores rows.

    Cutoff is 30 days before *now* (UTC). period_* are UTC dates for that window.
    """
    end = now or utc_now()
    cutoff = end - timedelta(days=30)
    return cutoff, end, cutoff.date(), end.date()


def compliance_score_percent(passed_runs: int, total_runs: int) -> float | None:
    """Return score 0–100, or None if there are no runs."""
    if total_runs <= 0:
        return None
    return round(100.0 * passed_runs / total_runs, 2)


def violation_count(failed_runs: int, error_runs: int) -> int:
    """Treat failed and error runs as violations (non-pass outcomes)."""
    return failed_runs + error_runs


def sparkline_svg_points(vals: list[float], width: float = 72, height: float = 20) -> str | None:
    """Points string for an SVG polyline sparkline, or None if not enough data."""
    if len(vals) < 2:
        return None
    vmin = min(vals)
    vmax = max(vals)
    vrange = vmax - vmin if vmax != vmin else 1.0
    parts: list[str] = []
    n = len(vals)
    for i, v in enumerate(vals):
        x = round(i * width / (n - 1), 1)
        y = round(height - ((v - vmin) / vrange * (height - 4) + 2), 1)
        parts.append(f"{x},{y}")
    return " ".join(parts)
