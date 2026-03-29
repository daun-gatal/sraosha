import sys
from unittest.mock import MagicMock, patch

from sraosha.core.runner import ContractRunner

mock_dc_module = MagicMock()
sys.modules.setdefault("datacontract", mock_dc_module)
sys.modules.setdefault("datacontract.data_contract", mock_dc_module)


class TestContractRunner:
    @patch("datacontract.data_contract.DataContract")
    def test_run_passing(self, mock_dc_class):
        mock_check = MagicMock()
        mock_check.result = "passed"
        mock_check.type = "schema"
        mock_check.field = "order_id"

        mock_result = MagicMock()
        mock_result.result = "passed"
        mock_result.checks = [mock_check]

        mock_instance = MagicMock()
        mock_instance.test.return_value = mock_result
        mock_dc_class.return_value = mock_instance

        runner = ContractRunner("fake/path.yaml")
        result = runner.run()

        assert result["passed"] is True
        assert result["checks_total"] == 1
        assert result["checks_passed"] == 1
        assert result["checks_failed"] == 0
        assert result["failures"] == []
        assert result["duration_seconds"] >= 0

    @patch("datacontract.data_contract.DataContract")
    def test_run_failing(self, mock_dc_class):
        mock_check_pass = MagicMock()
        mock_check_pass.result = "passed"
        mock_check_pass.type = "schema"
        mock_check_pass.field = "order_id"

        mock_check_fail = MagicMock()
        mock_check_fail.result = "failed"
        mock_check_fail.type = "quality"
        mock_check_fail.field = "order_total"
        mock_check_fail.reason = "Negative values found"

        mock_result = MagicMock()
        mock_result.result = "failed"
        mock_result.checks = [mock_check_pass, mock_check_fail]

        mock_instance = MagicMock()
        mock_instance.test.return_value = mock_result
        mock_dc_class.return_value = mock_instance

        runner = ContractRunner("fake/path.yaml")
        result = runner.run()

        assert result["passed"] is False
        assert result["checks_total"] == 2
        assert result["checks_passed"] == 1
        assert result["checks_failed"] == 1
        assert len(result["failures"]) == 1
        assert result["failures"][0]["check"] == "quality"
        assert result["failures"][0]["field"] == "order_total"

    @patch("datacontract.data_contract.DataContract")
    def test_run_no_checks(self, mock_dc_class):
        mock_result = MagicMock()
        mock_result.result = "passed"
        mock_result.checks = []

        mock_instance = MagicMock()
        mock_instance.test.return_value = mock_result
        mock_dc_class.return_value = mock_instance

        runner = ContractRunner("fake/path.yaml")
        result = runner.run()

        assert result["passed"] is True
        assert result["checks_total"] == 0
