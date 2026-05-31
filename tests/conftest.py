import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    def _load(name: str) -> dict:
        with (FIXTURES / name).open(encoding="utf-8") as f:
            return json.load(f)

    return _load
