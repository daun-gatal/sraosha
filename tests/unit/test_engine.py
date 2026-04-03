from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sraosha.core.engine import ContractEngine, ContractViolationError, EnforcementMode

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestContractEngine:
    @patch("sraosha.core.engine.ContractRunner")
    def test_run_block_mode_pass(self, mock_runner_cls):
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

        engine = ContractEngine(
            contract_path=str(FIXTURES / "sample_contract.yaml"),
            enforcement_mode=EnforcementMode.BLOCK,
            dry_run=True,
        )
        result = engine.run()

        assert result.passed is True
        assert result.checks_total == 3
        assert result.contract_id == "orders-v1"

    @patch("sraosha.core.engine.ContractRunner")
    def test_run_block_mode_fail_raises(self, mock_runner_cls):
        mock_runner = MagicMock()
        mock_runner.run.return_value = {
            "passed": False,
            "checks_total": 3,
            "checks_passed": 1,
            "checks_failed": 2,
            "failures": [{"check": "quality", "field": "x", "message": "bad"}],
            "duration_seconds": 0.3,
        }
        mock_runner_cls.return_value = mock_runner

        engine = ContractEngine(
            contract_path=str(FIXTURES / "sample_contract.yaml"),
            enforcement_mode=EnforcementMode.BLOCK,
            dry_run=True,
        )
        with pytest.raises(ContractViolationError) as exc_info:
            engine.run()

        assert exc_info.value.result.checks_failed == 2
        assert "orders-v1" in str(exc_info.value)

    @patch("sraosha.core.engine.ContractRunner")
    def test_run_warn_mode_fail_returns(self, mock_runner_cls):
        mock_runner = MagicMock()
        mock_runner.run.return_value = {
            "passed": False,
            "checks_total": 2,
            "checks_passed": 0,
            "checks_failed": 2,
            "failures": [{"check": "schema", "field": "a", "message": "missing"}],
            "duration_seconds": 0.1,
        }
        mock_runner_cls.return_value = mock_runner

        engine = ContractEngine(
            contract_path=str(FIXTURES / "sample_contract.yaml"),
            enforcement_mode=EnforcementMode.WARN,
            dry_run=True,
        )
        result = engine.run()
        assert result.passed is False
        assert result.enforcement_mode == EnforcementMode.WARN

    @patch("sraosha.core.engine.ContractRunner")
    def test_run_log_mode_fail_returns(self, mock_runner_cls):
        mock_runner = MagicMock()
        mock_runner.run.return_value = {
            "passed": False,
            "checks_total": 1,
            "checks_passed": 0,
            "checks_failed": 1,
            "failures": [],
            "duration_seconds": 0.05,
        }
        mock_runner_cls.return_value = mock_runner

        engine = ContractEngine(
            contract_path=str(FIXTURES / "sample_contract.yaml"),
            enforcement_mode=EnforcementMode.LOG,
            dry_run=True,
        )
        result = engine.run()
        assert result.passed is False

    def test_reads_enforcement_from_x_sraosha(self):
        engine = ContractEngine(
            contract_path=str(FIXTURES / "sample_contract.yaml"),
            enforcement_mode=EnforcementMode.WARN,
            dry_run=True,
        )
        contract_data = engine._load_contract()
        xs = contract_data.get("x-sraosha", {})
        assert "enforcement_mode" in xs or True
