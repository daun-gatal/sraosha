"""Standalone example: validate a contract from Python code."""

from sraosha.core.engine import ContractEngine, ContractViolationError, EnforcementMode


def main():
    engine = ContractEngine(
        contract_path="tests/fixtures/sample_contract.yaml",
        enforcement_mode=EnforcementMode.WARN,
        dry_run=True,
    )

    try:
        result = engine.run()
        print(f"Contract: {result.contract_id}")
        print(f"Passed: {result.passed}")
        print(f"Checks: {result.checks_passed}/{result.checks_total}")
        if result.failures:
            print("Failures:")
            for f in result.failures:
                print(f"  - {f['check']}: {f['message']}")
    except ContractViolationError as exc:
        print(f"BLOCKED: {exc}")


if __name__ == "__main__":
    main()
