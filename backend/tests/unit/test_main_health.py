import backend.tests.unit.ml_stubs  # noqa: F401

from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.main as main_module


def test_health_returns_200_when_redis_down_but_database_up():
    with patch.object(main_module, "check_redis_health", return_value=False):
        client = TestClient(main_module.app)
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["redis"] is False
    assert body["status"] == "degraded"
    assert body["database"] is True


def test_health_returns_200_when_redis_not_configured():
    with patch.object(main_module, "check_redis_health", return_value=None):
        client = TestClient(main_module.app)
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["redis"] is None
    assert body["status"] == "ok"


def test_health_returns_503_when_database_down():
    with patch.object(main_module, "check_redis_health", return_value=True), patch.object(
        main_module.engine, "connect", side_effect=Exception("db down")
    ):
        client = TestClient(main_module.app)
        response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["database"] is False
    assert body["status"] == "unhealthy"
