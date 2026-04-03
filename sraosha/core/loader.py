import logging
import tempfile
from pathlib import Path
from typing import Any, cast

import httpx
import yaml

logger = logging.getLogger(__name__)


class ContractLoader:
    """
    Loads a datacontract.yaml from various sources.
    Supported: local file path, HTTP/HTTPS URL, Git repo URL (auto-clones)
    """

    @staticmethod
    def from_file(path: str | Path) -> dict:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Contract file not found: {path}")
        return cast(dict[Any, Any], yaml.safe_load(p.read_text(encoding="utf-8")))

    @staticmethod
    def from_url(url: str) -> dict:
        resp = httpx.get(url, follow_redirects=True, timeout=30.0)
        resp.raise_for_status()
        return cast(dict[Any, Any], yaml.safe_load(resp.text))

    @staticmethod
    def from_git(repo_url: str, file_path: str, branch: str = "main") -> dict:
        try:
            import git
        except ImportError:
            raise ImportError(
                "gitpython is required for loading contracts from git repos. "
                "Install it with: pip install gitpython"
            ) from None

        with tempfile.TemporaryDirectory() as tmp:
            git.Repo.clone_from(repo_url, tmp, branch=branch, depth=1)
            full_path = Path(tmp) / file_path
            if not full_path.exists():
                raise FileNotFoundError(
                    f"File '{file_path}' not found in repo '{repo_url}' (branch={branch})"
                )
            return cast(dict[Any, Any], yaml.safe_load(full_path.read_text(encoding="utf-8")))

    @staticmethod
    def auto(source: str) -> dict:
        if source.startswith("git+https://") or source.startswith("git+http://"):
            clean = source.replace("git+", "", 1)
            parts = clean.split("//", 1)
            if len(parts) == 2 and ":" in parts[1]:
                repo_part, file_path = parts[1].rsplit(":", 1)
                repo_url = parts[0] + "//" + repo_part
            else:
                raise ValueError(
                    f"Invalid git source format: {source}. "
                    "Expected: git+https://host/repo:path/to/file.yaml"
                )
            return ContractLoader.from_git(repo_url, file_path)
        elif source.startswith("http://") or source.startswith("https://"):
            return ContractLoader.from_url(source)
        else:
            return ContractLoader.from_file(source)
