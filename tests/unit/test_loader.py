from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sraosha.core.loader import ContractLoader

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestFromFile:
    def test_loads_valid_yaml(self):
        data = ContractLoader.from_file(FIXTURES / "sample_contract.yaml")
        assert data["id"] == "orders-v1"
        assert data["info"]["title"] == "Orders"

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            ContractLoader.from_file("/nonexistent/path.yaml")


class TestFromUrl:
    @patch("sraosha.core.loader.httpx.get")
    def test_loads_from_url(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = "id: remote-v1\ninfo:\n  title: Remote\n  version: 1.0.0"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        data = ContractLoader.from_url("https://example.com/contract.yaml")
        assert data["id"] == "remote-v1"
        mock_get.assert_called_once()


class TestFromGit:
    @patch("git.Repo.clone_from")
    def test_loads_from_git(self, mock_clone, tmp_path):
        contract_file = tmp_path / "contract.yaml"
        contract_file.write_text("id: git-v1\ninfo:\n  title: Git\n  version: 1.0.0")

        def clone_side_effect(url, to_path, **kwargs):
            dest = Path(to_path) / "contract.yaml"
            dest.write_text(contract_file.read_text())
            return MagicMock()

        mock_clone.side_effect = clone_side_effect

        data = ContractLoader.from_git("https://github.com/org/repo.git", "contract.yaml")
        assert data["id"] == "git-v1"


class TestAuto:
    def test_auto_detects_local_file(self):
        path = str(FIXTURES / "sample_contract.yaml")
        data = ContractLoader.auto(path)
        assert data["id"] == "orders-v1"

    @patch("sraosha.core.loader.httpx.get")
    def test_auto_detects_https(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = "id: url-v1\ninfo:\n  title: URL\n  version: 1.0.0"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        data = ContractLoader.auto("https://example.com/contract.yaml")
        assert data["id"] == "url-v1"
