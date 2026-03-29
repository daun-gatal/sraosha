"""Airflow operator for Sraosha contract validation.

Requires the `airflow` optional dependency:
    pip install sraosha[airflow]
"""

from __future__ import annotations

import logging
from typing import Any

try:
    from airflow.models import BaseOperator
except ImportError:
    raise ImportError(
        "Apache Airflow is required for SraoshaOperator. "
        "Install with: pip install sraosha[airflow]"
    )

from sraosha.core.engine import ContractEngine, ContractViolationError, EnforcementMode

logger = logging.getLogger(__name__)


class SraoshaOperator(BaseOperator):
    """
    Airflow operator that validates a data contract before or after a task.

    Usage in DAG::

        validate_orders = SraoshaOperator(
            task_id="validate_orders_contract",
            contract_path="contracts/orders.yaml",
            enforcement_mode="block",
            server="production",
            dag=dag,
        )
        load_orders >> validate_orders >> transform_orders
    """

    template_fields = ("contract_path", "server")
    ui_color = "#6366f1"

    def __init__(
        self,
        contract_path: str,
        enforcement_mode: str = "block",
        server: str | None = None,
        sraosha_api_url: str | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.contract_path = contract_path
        self.enforcement_mode = EnforcementMode(enforcement_mode)
        self.server = server
        self.sraosha_api_url = sraosha_api_url

    def execute(self, context: dict) -> dict:
        logger.info(
            "Sraosha: validating contract %s (mode=%s)",
            self.contract_path,
            self.enforcement_mode.value,
        )

        engine = ContractEngine(
            contract_path=self.contract_path,
            enforcement_mode=self.enforcement_mode,
            server=self.server,
        )

        try:
            result = engine.run()
        except ContractViolationError:
            raise

        if self.sraosha_api_url:
            self._push_to_api(result)

        return {
            "passed": result.passed,
            "checks_total": result.checks_total,
            "checks_passed": result.checks_passed,
            "checks_failed": result.checks_failed,
            "contract_id": result.contract_id,
            "run_id": result.run_id,
        }

    def _push_to_api(self, result) -> None:
        try:
            import httpx

            httpx.post(
                f"{self.sraosha_api_url}/api/v1/runs",
                json={
                    "contract_id": result.contract_id,
                    "status": "passed" if result.passed else "failed",
                    "enforcement_mode": result.enforcement_mode.value,
                    "checks_total": result.checks_total,
                    "checks_passed": result.checks_passed,
                    "checks_failed": result.checks_failed,
                    "failures": result.failures,
                    "duration_ms": int(result.duration_seconds * 1000),
                    "triggered_by": "airflow",
                },
                timeout=10.0,
            )
        except Exception:
            logger.exception("Failed to push results to Sraosha API at %s", self.sraosha_api_url)
