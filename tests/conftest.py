from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_contract_path() -> Path:
    return FIXTURES_DIR / "sample_contract.yaml"


@pytest.fixture
def broken_contract_path() -> Path:
    return FIXTURES_DIR / "sample_contract_broken.yaml"
