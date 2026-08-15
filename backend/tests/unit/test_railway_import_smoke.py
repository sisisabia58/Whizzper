import subprocess
import sys


def test_modal_factory_subprocess_has_no_torch():
    code = r"""
import os
os.environ["MODAL_WEB_ENDPOINT_URL"] = "https://mock-endpoint.modal.run"
from modules.whisper.whisper_factory import WhisperFactory
inf = WhisperFactory.create_whisper_inference("faster-whisper", output_dir="/tmp")
assert inf.device == "modal-gpu"
import sys
assert "torch" not in sys.modules
assert "faster_whisper" not in sys.modules
assert "gradio" not in sys.modules
"""
    proc = subprocess.run([sys.executable, "-c", code], cwd=".", capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
