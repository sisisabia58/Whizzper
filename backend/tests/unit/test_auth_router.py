import backend.tests.unit.ml_stubs  # noqa: F401

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_auth_start_returns_state():
    from backend.main import app

    client = TestClient(app)
    response = client.get("/api/auth/google/start?owner_key=user1")
    assert response.status_code == 200
    data = response.json()
    assert "authorize_url" in data
    assert "state" in data
    assert len(data["state"]) > 0


def test_auth_callback_rejects_invalid_state():
    from backend.main import app

    client = TestClient(app)
    response = client.get("/api/auth/google/callback?code=fake&state=invalid-state")
    assert response.status_code == 400
