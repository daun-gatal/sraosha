"""Pluggable data-quality execution interface."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from sraosha.dq.result import DQRunResult


@runtime_checkable
class DQRunner(Protocol):
    """Runs checks against a data source (e.g. Soda Core)."""

    def run(
        self,
        data_source_name: str,
        server_type: str,
        conn_params: dict[str, Any],
        sodacl_yaml: str,
    ) -> DQRunResult:
        """Execute checks and return a normalized result."""
        ...
