import importlib.util
from pathlib import Path

_ml_stubs_path = Path(__file__).resolve().parent / "unit" / "ml_stubs.py"
_spec = importlib.util.spec_from_file_location("_ml_stubs", _ml_stubs_path)
_ml_stubs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ml_stubs)

import pytest
from unittest.mock import MagicMock

@pytest.fixture
def scratch_db():
    from sqlalchemy import create_engine
    engine = create_engine("sqlite:///:memory:")
    return engine

@pytest.fixture
def fake_pipeline():
    mock = MagicMock()
    mock.run.return_value = ([], 1.0)
    return mock
