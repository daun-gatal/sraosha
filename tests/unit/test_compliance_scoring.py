"""Unit tests for compliance scoring helpers."""

from datetime import datetime, timedelta, timezone

import pytest

from sraosha.compliance.scoring import (
    compliance_score_percent,
    rolling_30d_window,
    sparkline_svg_points,
    violation_count,
)


def test_compliance_score_percent() -> None:
    assert compliance_score_percent(3, 10) == 30.0
    assert compliance_score_percent(10, 10) == 100.0
    assert compliance_score_percent(0, 5) == 0.0
    assert compliance_score_percent(0, 0) is None


def test_violation_count() -> None:
    assert violation_count(2, 1) == 3
    assert violation_count(0, 0) == 0


def test_sparkline_svg_points() -> None:
    assert sparkline_svg_points([80.0, 90.0]) is not None
    assert sparkline_svg_points([80.0]) is None
    pts = sparkline_svg_points([10.0, 20.0, 30.0])
    assert pts is not None
    assert "72" in pts


def test_rolling_30d_window() -> None:
    fixed = datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc)
    cutoff, end, p_start, p_end = rolling_30d_window(fixed)
    assert end == fixed
    assert (fixed - cutoff) == timedelta(days=30)
    assert p_end == fixed.date()
    assert p_start == cutoff.date()


@pytest.mark.parametrize(
    ("vals", "expected"),
    [
        ([1.0, 2.0], True),
        ([1.0], False),
        ([], False),
    ],
)
def test_sparkline_length(vals: list[float], expected: bool) -> None:
    assert (sparkline_svg_points(vals) is not None) == expected
