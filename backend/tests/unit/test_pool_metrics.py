import sys
from unittest.mock import MagicMock

# Mock heavy ML modules so fast backend unit tests run isolated
sys.modules["modules.whisper.faster_whisper_inference"] = MagicMock()
sys.modules["modules.vad.silero_vad_inference"] = MagicMock()
sys.modules["modules.uvr.music_separator"] = MagicMock()
sys.modules["modules.diarize.diarizer"] = MagicMock()

import pytest
from fastapi.testclient import TestClient

def test_health_includes_pool_status(monkeypatch):
    mock_pool = MagicMock()
    mock_pool.endpoints = ["https://ep1.modal.run", "https://ep2.modal.run"]
    mock_pool.counters.get.return_value = 1
    mock_pool.healthy_endpoints.return_value = ["https://ep1.modal.run"]
    mock_pool._consecutive_failures = {"https://ep1.modal.run": 0, "https://ep2.modal.run": 3}
    
    monkeypatch.setattr("backend.routers.transcription.router.modal_pool", mock_pool)
    
    from backend.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "pool" in data
    assert len(data["pool"]) == 2
    assert data["pool"][0]["endpoint"] == "https://ep1.modal.run"
    assert data["pool"][0]["inflight"] == 1
    assert data["pool"][0]["healthy"] is True
