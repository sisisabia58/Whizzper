import ast
from pathlib import Path

FORBIDDEN = {"torch", "torchaudio", "gradio", "gradio_i18n", "faster_whisper", "whisper", "pyannote"}


def _top_level_roots(path: str) -> set[str]:
    tree = ast.parse(Path(path).read_text())
    roots: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_constants_has_no_gradio_i18n():
    assert "gradio_i18n" not in _top_level_roots("modules/utils/constants.py")


def test_data_classes_has_no_ml_imports():
    roots = _top_level_roots("modules/whisper/data_classes.py")
    assert not (roots & FORBIDDEN)


def test_modal_whisper_inference_has_no_base_pipeline_import():
    roots = _top_level_roots("modules/whisper/modal_whisper_inference.py")
    assert "gradio" not in roots
    src = Path("modules/whisper/modal_whisper_inference.py").read_text()
    assert "from modules.whisper.base_transcription_pipeline import" not in src


def test_whisper_factory_does_not_import_torch_at_module_level():
    roots = _top_level_roots("modules/whisper/whisper_factory.py")
    assert "torch" not in roots


def test_requirements_railway_omits_gpu_stack():
    lines = [
        ln.strip().lower().split("==")[0].split(">=")[0].split("[")[0]
        for ln in Path("requirements-railway.txt").read_text().splitlines()
        if ln.strip() and not ln.strip().startswith("#") and not ln.strip().startswith("--")
    ]
    forbidden = {
        "torch",
        "torchaudio",
        "openai-whisper",
        "faster-whisper",
        "transformers",
        "pyannote.audio",
        "gradio",
        "gradio-i18n",
        "matplotlib",
    }
    assert not (set(lines) & forbidden)
