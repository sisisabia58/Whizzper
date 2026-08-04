import backend.tests.unit.ml_stubs  # noqa: F401

from backend.common.oauth_state import create_state, validate_state


def test_oauth_state_validates_once():
    state = create_state()
    assert validate_state(state) is True
    assert validate_state(state) is False


def test_oauth_state_rejects_unknown():
    assert validate_state("not-a-real-state") is False
