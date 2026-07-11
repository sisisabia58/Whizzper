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

import pytest
from fastapi.testclient import TestClient

def test_folders_requires_connection_id():
    from backend.main import app
    client = TestClient(app)
    response = client.get("/api/drive/folders")
    assert response.status_code == 422

def test_folders_connection_not_found():
    from backend.main import app
    client = TestClient(app)
    response = client.get("/api/drive/folders?connection_id=missing-id")
    assert response.status_code == 404
