"""Normalized data-quality run outcome (backend-agnostic)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DQRunResult:
    status: str
    checks_total: int
    checks_passed: int
    checks_warned: int
    checks_failed: int
    results: list[dict[str, Any]]
    diagnostics: list[dict[str, Any]]
    log: str
    duration_seconds: float
