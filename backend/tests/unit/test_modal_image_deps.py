from pathlib import Path


def test_modal_image_explicitly_installs_gradio():
    src = Path("modal_app.py").read_text()
    assert "gradio==5.29.0" in src
    assert "import gradio as gr" not in src


def test_modal_gpu_uses_direct_faster_whisper_path():
    src = Path("modal_app.py").read_text()
    assert "def _transcribe_direct(" in src
    assert "faster_whisper.WhisperModel" in src
    assert 'gpu=["T4", "L4", "A10", "any"]' in src
    assert '"PYTHONPATH": "/root"' in src
