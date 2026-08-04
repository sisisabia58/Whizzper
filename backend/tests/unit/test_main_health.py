import backend.tests.unit.ml_stubs  # noqa: F401

from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.main as main_module


def test_health_reports_redis_down_when_ping_fails():
    with patch.object(main_module, "check_redis_health", return_value=False):
        client = TestClient(main_module.app)
        response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["redis"] is False
    assert body["status"] == "degraded"


def test_health_reports_redis_up_when_ping_succeeds():
    with patch.object(main_module, "check_redis_health", return_value=True):
        client = TestClient(main_module.app)
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["redis"] is True
