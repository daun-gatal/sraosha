"""Integration tests for SraoshaOperator using mocked Airflow + engine."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sraosha.core.engine import ContractViolationError, EnforcementMode, ValidationResult

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _make_result(passed: bool, contract_id: str = "orders-v1") -> ValidationResult:
    return ValidationResult(
        contract_id=contract_id,
        contract_path="fake/path.yaml",
        passed=passed,
        enforcement_mode=EnforcementMode.BLOCK,
        checks_total=3,
        checks_passed=3 if passed else 1,
        checks_failed=0 if passed else 2,
        failures=[] if passed else [{"check": "q", "field": "x", "message": "bad"}],
        duration_seconds=0.5,
    )


class TestSraoshaOperatorMocked:
    """Tests that mock away Airflow's BaseOperator import."""

    @patch("sraosha.core.engine.ContractRunner")
    def test_operator_pass(self, mock_runner_cls):
        mock_runner = MagicMock()
        mock_runner.run.return_value = {
            "passed": True,
            "checks_total": 3,
            "checks_passed": 3,
            "checks_failed": 0,
            "failures": [],
            "duration_seconds": 0.5,
        }
        mock_runner_cls.return_value = mock_runner

        from sraosha.hooks.base import BasePipelineHook

        class TestHook(BasePipelineHook):
            def on_success(self, result):
                self.success_called = True

            def on_failure(self, result):
                self.failure_called = True

        hook = TestHook(
            contract_path=str(FIXTURES / "sample_contract.yaml"),
            enforcement_mode=EnforcementMode.WARN,
        )
        result = hook.execute()
        assert result.passed is True
        assert hook.success_called is True

    @patch("sraosha.core.engine.ContractRunner")
    def test_operator_fail_warn(self, mock_runner_cls):
        mock_runner = MagicMock()
        mock_runner.run.return_value = {
            "passed": False,
            "checks_total": 2,
            "checks_passed": 0,
            "checks_failed": 2,
            "failures": [{"check": "q", "field": "x", "message": "bad"}],
            "duration_seconds": 0.3,
        }
        mock_runner_cls.return_value = mock_runner

        from sraosha.hooks.base import BasePipelineHook

        class TestHook(BasePipelineHook):
            def on_success(self, result):
                self.success_called = True

            def on_failure(self, result):
                self.failure_called = True

        hook = TestHook(
            contract_path=str(FIXTURES / "sample_contract.yaml"),
            enforcement_mode=EnforcementMode.WARN,
        )
        result = hook.execute()
        assert result.passed is False
        assert hook.failure_called is True

    @patch("sraosha.core.engine.ContractRunner")
    def test_operator_fail_block(self, mock_runner_cls):
        mock_runner = MagicMock()
        mock_runner.run.return_value = {
            "passed": False,
            "checks_total": 2,
            "checks_passed": 0,
            "checks_failed": 2,
            "failures": [{"check": "q", "field": "x", "message": "bad"}],
            "duration_seconds": 0.3,
        }
        mock_runner_cls.return_value = mock_runner

        from sraosha.hooks.base import BasePipelineHook

        class TestHook(BasePipelineHook):
            def on_success(self, result):
                pass

            def on_failure(self, result):
                pass

        hook = TestHook(
            contract_path=str(FIXTURES / "sample_contract.yaml"),
            enforcement_mode=EnforcementMode.BLOCK,
        )
        with pytest.raises(ContractViolationError):
            hook.execute()
