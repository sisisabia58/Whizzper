import sys
import os
import types
import numpy as np
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
def test_numpy_array_ffmpeg_compression(mock_run):
    # Create a simple numpy array representing 1 second of audio at 16kHz
    audio = np.zeros(16000, dtype=np.float32)
    
    inference = ModalWhisperInference()
    inference.endpoint_url = "https://mock.modal.run"
    
    # Mock the post request and file reads
    with patch("requests.post") as mock_post, \
         patch("builtins.open", MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(read=lambda: b"mock-mp3-bytes"))))), \
         patch("os.path.exists", return_value=True), \
         patch("os.remove") as mock_remove:
        
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"segments": [], "elapsed_time": 0.0}
        
        inference.run(audio, MagicMock(), "SRT", False, None)
        
        # Verify that ffmpeg was called to output an .mp3 file
        assert mock_run.called
        called_args = mock_run.call_args[0][0]
        assert "ffmpeg" in called_args
        assert "libmp3lame" in called_args
        assert "32k" in called_args
