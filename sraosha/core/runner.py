import logging
import time

logger = logging.getLogger(__name__)


class ContractRunner:
    """
    Wraps datacontract-cli's DataContract class.
    Normalizes its output into Sraosha's ValidationResult format.
    """

    def __init__(self, contract_path: str, server: str | None = None):
        self.contract_path = contract_path
        self.server = server

    def run(self) -> dict:
        from datacontract.data_contract import DataContract

        dc = DataContract(data_contract_file=self.contract_path)

        start = time.monotonic()
        try:
            run_result = dc.test()
        except Exception as exc:
            logger.error("datacontract-cli test failed: %s", exc)
            raise

        duration = time.monotonic() - start

        checks_total = 0
        checks_passed = 0
        checks_failed = 0
        failures: list[dict] = []

        if hasattr(run_result, "checks") and run_result.checks is not None:
            for check in run_result.checks:
                checks_total += 1
                passed = getattr(check, "result", None) == "passed"
                if passed:
                    checks_passed += 1
                else:
                    checks_failed += 1
                    failures.append(
                        {
                            "check": getattr(check, "type", str(check)),
                            "field": getattr(check, "field", None),
                            "message": getattr(check, "reason", "Check failed"),
                        }
                    )

        result_str = getattr(run_result, "result", "unknown")
        passed = result_str == "passed" if checks_total == 0 else checks_failed == 0

        return {
            "passed": passed,
            "checks_total": checks_total,
            "checks_passed": checks_passed,
            "checks_failed": checks_failed,
            "failures": failures,
            "duration_seconds": round(duration, 3),
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run data contract validation")
    parser.add_argument("--contract", required=True, help="Path to contract YAML")
    parser.add_argument("--server", default=None, help="Server block to test against")
    args = parser.parse_args()

    runner = ContractRunner(args.contract, server=args.server)
    result = runner.run()
    print(result)  # noqa: T201
