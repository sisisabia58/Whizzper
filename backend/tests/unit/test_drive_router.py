import sys
import os
import types
from importlib.machinery import ModuleSpec
from unittest.mock import MagicMock

# Prevent local model/pipeline weight loading during unit tests
os.environ["MODAL_WEB_ENDPOINT_URL"] = "https://mock-endpoint.modal.run"

# Stub pyannote and torchaudio as real ModuleType instances with ModuleSpec
for name in ['torchaudio', 'pyannote', 'pyannote.audio', 'pyannote.audio.core', 'pyannote.audio.core.io']:
    mod = types.ModuleType(name)
    mod.__spec__ = ModuleSpec(name, None)
    sys.modules[name] = mod

sys.modules['torchaudio'].AudioMetaData = object
sys.modules['pyannote.audio'].Pipeline = MagicMock()

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_scan_invalid_url():
    # Empty payload
    response = client.post("/api/drive/scan", json={})
    assert response.status_code == 400
    assert "Missing folder_url" in response.json()["detail"]

    # Invalid URL format
    response = client.post("/api/drive/scan", json={"folder_url": "https://google.com"})
    assert response.status_code == 400
    assert "Invalid Google Drive folder link" in response.json()["detail"]

def test_scan_api_key_missing():
    # Since GOOGLE_DRIVE_API_KEY is not configured in unit tests, we expect a 502 error indicating missing configuration / call failure.
    response = client.post("/api/drive/scan", json={"folder_url": "https://drive.google.com/drive/folders/test-folder-id"})
    assert response.status_code == 502
    assert "scan failed" in response.json()["detail"].lower()
