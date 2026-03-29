"""dbt hook runner for Sraosha contract validation.

Can be invoked:
  1. From a dbt macro (compiles to a shell call)
  2. Directly from Python after dbt run completes
"""

import logging
import sys

from sraosha.core.engine import ContractEngine, ContractViolationError, EnforcementMode

logger = logging.getLogger(__name__)


class DbtHook:
    """Runs Sraosha validation as part of a dbt run lifecycle."""

    def __init__(self, contract_path: str, enforcement_mode: str = "block"):
        self.contract_path = contract_path
        self.enforcement_mode = EnforcementMode(enforcement_mode)

    def run(self) -> None:
        logger.info(
            "Sraosha dbt hook: validating %s (mode=%s)",
            self.contract_path,
            self.enforcement_mode.value,
        )

        engine = ContractEngine(
            contract_path=self.contract_path,
            enforcement_mode=self.enforcement_mode,
        )

        try:
            result = engine.run()
            if result.passed:
                logger.info(
                    "Contract '%s' passed: %d/%d checks OK",
                    result.contract_id,
                    result.checks_passed,
                    result.checks_total,
                )
            else:
                logger.warning(
                    "Contract '%s' failed: %d/%d checks failed",
                    result.contract_id,
                    result.checks_failed,
                    result.checks_total,
                )
        except ContractViolationError as exc:
            logger.error("Contract violation (BLOCK mode): %s", exc)
            sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sraosha dbt hook")
    parser.add_argument("--contract", required=True, help="Path to contract YAML")
    parser.add_argument("--mode", default="block", choices=["block", "warn", "log"])
    args = parser.parse_args()

    hook = DbtHook(contract_path=args.contract, enforcement_mode=args.mode)
    hook.run()
