"""Backward-compatible exports for data-quality execution.

Prefer :func:`sraosha.dq.factory.get_dq_runner` for new code.
"""

from __future__ import annotations

from sraosha.dq.backends.soda import SodaCheckRunner
from sraosha.dq.factory import get_dq_runner
from sraosha.dq.protocol import DQRunner
from sraosha.dq.result import DQRunResult

__all__ = ["DQRunResult", "DQRunner", "SodaCheckRunner", "get_dq_runner"]
