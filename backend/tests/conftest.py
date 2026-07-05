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
