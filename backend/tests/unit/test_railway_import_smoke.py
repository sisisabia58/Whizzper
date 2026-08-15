import subprocess
import sys

_BLOCKED_IMPORT_SMOKE = r"""
import os
import sys

os.environ["MODAL_WEB_ENDPOINT_URL"] = "https://mock-endpoint.modal.run"
os.environ["TEST_ENV"] = "true"
os.environ["DB_URL"] = "sqlite:///:memory:"
os.environ.pop("REDIS_URL", None)

BLOCKED = {
    "torch",
    "torchaudio",
    "gradio",
    "gradio_i18n",
    "faster_whisper",
    "whisper",
    "pyannote",
    "transformers",
    "matplotlib",
}


class _BlockGpuStack:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in BLOCKED:
            raise ImportError(f"blocked {fullname} (Railway CPU image)")
        return None


sys.meta_path.insert(0, _BlockGpuStack())
for name in list(sys.modules):
    if name.split(".")[0] in BLOCKED:
        del sys.modules[name]
"""


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


def test_backend_main_imports_without_gpu_stack():
    code = _BLOCKED_IMPORT_SMOKE + r"""
from fastapi.testclient import TestClient
import backend.main
assert backend.main.app is not None
assert "gradio" not in sys.modules
assert "torch" not in sys.modules
with TestClient(backend.main.app) as client:
    response = client.get("/health")
assert response.status_code == 200
assert response.json()["database"] is True
"""
    proc = subprocess.run([sys.executable, "-c", code], cwd=".", capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_celery_app_imports_without_gpu_stack():
    code = _BLOCKED_IMPORT_SMOKE + r"""
from backend.queue.celery_app import celery_app
assert celery_app is not None
assert "gradio" not in sys.modules
assert "torch" not in sys.modules
"""
    proc = subprocess.run([sys.executable, "-c", code], cwd=".", capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
