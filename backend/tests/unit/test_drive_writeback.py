import sys
import os
import types
from importlib.machinery import ModuleSpec
from unittest.mock import MagicMock, patch

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
from modules.utils.drive_manager import DriveManager

def test_upload_srt_arguments():
    manager = DriveManager()
    manager.service = MagicMock()
    manager.service.files().create().execute.return_value = {"id": "new-srt-file-id"}
    
    file_id = manager.upload_srt("test.srt", "1\n00:00:01 --> 00:00:05\nHello", "folder-123", "version")
    assert file_id == "new-srt-file-id"
