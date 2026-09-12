from pathlib import Path


def test_modal_image_explicitly_installs_gradio():
    src = Path("modal_app.py").read_text()
    assert "gradio==5.29.0" in src
    assert "import gradio as gr" not in src
