from fastapi.testclient import TestClient


def test_health_endpoint():
    from backend.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code in [200, 503]
    json_data = response.json()
    assert "status" in json_data
    assert "database" in json_data
    assert "redis" in json_data


def test_metrics_endpoint():
    from backend.main import app

    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"whizzper_tasks_total" in response.content or b"process_cpu_seconds" in response.content
    assert b"whizzper_queue_depth" in response.content
    assert b"whizzper_batches_in_progress" in response.content
