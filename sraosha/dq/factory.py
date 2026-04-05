"""Resolve the :class:`sraosha.dq.protocol.DQRunner` implementation (Soda Core)."""

from __future__ import annotations

from sraosha.dq.protocol import DQRunner


def get_dq_runner() -> DQRunner:
    """Return the DQ runner (Soda Core)."""
    from sraosha.dq.backends.soda import SodaCheckRunner

    return SodaCheckRunner()
