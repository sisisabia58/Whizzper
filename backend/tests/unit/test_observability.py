import sys
from unittest.mock import MagicMock

# Mock heavy ML modules so fast backend unit tests run isolated
sys.modules["modules.whisper.faster_whisper_inference"] = MagicMock()
sys.modules["modules.vad.silero_vad_inference"] = MagicMock()
sys.modules["modules.uvr.music_separator"] = MagicMock()
sys.modules["modules.diarize.diarizer"] = MagicMock()

import pytest
from fastapi.testclient import TestClient
from backend.main import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code in [200, 503]
    json_data = response.json()
    assert "status" in json_data
    assert "database" in json_data
    assert "redis" in json_data


def test_metrics_endpoint():
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"whizzper_tasks_total" in response.content or b"process_cpu_seconds" in response.content
