"""Integration tests for DbtHook."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestDbtHook:
    @patch("sraosha.core.engine.ContractRunner")
    def test_dbt_hook_pass(self, mock_runner_cls):
        mock_runner = MagicMock()
        mock_runner.run.return_value = {
            "passed": True,
            "checks_total": 2,
            "checks_passed": 2,
            "checks_failed": 0,
            "failures": [],
            "duration_seconds": 0.1,
        }
        mock_runner_cls.return_value = mock_runner

        from sraosha.hooks.dbt.hook import DbtHook

        hook = DbtHook(
            contract_path=str(FIXTURES / "sample_contract.yaml"),
            enforcement_mode="warn",
        )
        hook.run()

    @patch("sraosha.core.engine.ContractRunner")
    def test_dbt_hook_fail_block_exits(self, mock_runner_cls):
        mock_runner = MagicMock()
        mock_runner.run.return_value = {
            "passed": False,
            "checks_total": 2,
            "checks_passed": 0,
            "checks_failed": 2,
            "failures": [{"check": "schema", "field": "id", "message": "missing"}],
            "duration_seconds": 0.1,
        }
        mock_runner_cls.return_value = mock_runner

        from sraosha.hooks.dbt.hook import DbtHook

        hook = DbtHook(
            contract_path=str(FIXTURES / "sample_contract.yaml"),
            enforcement_mode="block",
        )
        with pytest.raises(SystemExit) as exc_info:
            hook.run()
        assert exc_info.value.code == 1

    @patch("sraosha.core.engine.ContractRunner")
    def test_dbt_hook_fail_warn_continues(self, mock_runner_cls):
        mock_runner = MagicMock()
        mock_runner.run.return_value = {
            "passed": False,
            "checks_total": 1,
            "checks_passed": 0,
            "checks_failed": 1,
            "failures": [{"check": "schema", "field": "x", "message": "bad"}],
            "duration_seconds": 0.05,
        }
        mock_runner_cls.return_value = mock_runner

        from sraosha.hooks.dbt.hook import DbtHook

        hook = DbtHook(
            contract_path=str(FIXTURES / "sample_contract.yaml"),
            enforcement_mode="warn",
        )
        hook.run()
