import sys
import os
import types
from importlib.machinery import ModuleSpec
from unittest.mock import MagicMock, patch

# Prevent local model/pipeline weight loading during unit tests
os.environ["MODAL_WEB_ENDPOINT_URL"] = "https://mock-endpoint.modal.run"

# Stub pyannote and torchaudio
for name in ['torchaudio', 'pyannote', 'pyannote.audio', 'pyannote.audio.core', 'pyannote.audio.core.io']:
    mod = types.ModuleType(name)
    mod.__spec__ = ModuleSpec(name, None)
    sys.modules[name] = mod
sys.modules['torchaudio'].AudioMetaData = object
sys.modules['pyannote.audio'].Pipeline = MagicMock()

from modules.whisper.modal_whisper_inference import ModalWhisperInference

@patch("subprocess.run")
def test_filepath_mp3_always_compressed(mock_run):
    inference = ModalWhisperInference()
    inference.endpoint_url = "https://mock.modal.run"
    
    with patch("requests.post") as mock_post, \
         patch("builtins.open", MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(read=lambda: b"mock-mp3-bytes"))))), \
         patch("os.path.exists", return_value=True), \
         patch("os.remove"):
        
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"segments": [], "elapsed_time": 0.0}
        
        # Test with an already existing .mp3 file
        inference.run("episode1.mp3", MagicMock(), "SRT", False, None)
        
        # Verify that ffmpeg compression was still called to ensure low bitrate
        assert mock_run.called
        called_args = mock_run.call_args[0][0]
        assert "ffmpeg" in called_args
        assert "libmp3lame" in called_args
        assert "32k" in called_args
