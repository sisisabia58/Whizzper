"""Shared stubs so unit tests avoid loading GPU/ML dependencies when absent."""

import os
import sys
import types
from importlib.machinery import ModuleSpec
from importlib.util import find_spec
from unittest.mock import MagicMock

os.environ.setdefault("MODAL_WEB_ENDPOINT_URL", "https://mock-endpoint.modal.run")
os.environ.setdefault("DB_URL", "sqlite:///:memory:")


def _ensure_stub(name: str) -> None:
    if name in sys.modules:
        return
    try:
        if find_spec(name) is not None:
            return
    except (ModuleNotFoundError, AttributeError, ValueError):
        pass
    mod = types.ModuleType(name)
    mod.__spec__ = ModuleSpec(name, None)
    if "." not in name or name.count(".") == 0:
        mod.__path__ = []
    sys.modules[name] = mod


_OPTIONAL_STUBS = [
    "pyannote",
    "pyannote.audio",
    "pyannote.audio.core",
    "pyannote.audio.core.io",
]

for _name in _OPTIONAL_STUBS:
    _ensure_stub(_name)

if "pyannote.audio" in sys.modules and not hasattr(sys.modules["pyannote.audio"], "Pipeline"):
    sys.modules["pyannote.audio"].Pipeline = MagicMock()

_fw = types.ModuleType("faster_whisper")
_fw.__spec__ = ModuleSpec("faster_whisper", None)
_fw.__path__ = []
_fw.transcribe = types.ModuleType("faster_whisper.transcribe")
_fw.vad = types.ModuleType("faster_whisper.vad")
_fw.vad.VadOptions = MagicMock()
_fw.vad.get_vad_model = MagicMock()
sys.modules["faster_whisper"] = _fw
sys.modules["faster_whisper.transcribe"] = _fw.transcribe
sys.modules["faster_whisper.vad"] = _fw.vad

for _name in [
    "whisper",
    "torch",
    "torchaudio",
    "gradio_i18n",
    "modules.whisper.faster_whisper_inference",
    "modules.vad.silero_vad_inference",
    "modules.vad.silero_vad",
    "modules.uvr.music_separator",
    "modules.diarize.diarizer",
]:
    if _name not in sys.modules:
        sys.modules[_name] = MagicMock()

_gradio = types.ModuleType("gradio")
_gradio.__spec__ = ModuleSpec("gradio", None)
_gradio.__path__ = []
_gradio.utils = types.ModuleType("gradio.utils")
_gradio.utils.NamedString = MagicMock()
sys.modules["gradio"] = _gradio
sys.modules["gradio.utils"] = _gradio.utils

if "torchaudio" in sys.modules and not hasattr(sys.modules["torchaudio"], "AudioMetaData"):
    sys.modules["torchaudio"].AudioMetaData = object


def _install_whisper_router_stubs() -> None:
    """Minimal stubs so `backend.routers.transcription.router` imports without ML wheels."""
    from pydantic import BaseModel
    from typing import Optional

    class Segment(BaseModel):
        id: Optional[int] = None
        text: Optional[str] = None
        start: Optional[float] = None
        end: Optional[float] = None

    class _Params(BaseModel):
        model_config = {"extra": "allow"}

        def to_dict(self):
            return self.model_dump()

    dc = types.ModuleType("modules.whisper.data_classes")
    dc.Segment = Segment
    dc.WhisperParams = _Params
    dc.VadParams = _Params
    dc.BGMSeparationParams = _Params
    dc.DiarizationParams = _Params
    dc.TranscriptionPipelineParams = MagicMock()
    dc.Optional = Optional
    sys.modules["modules.whisper.data_classes"] = dc

    for _mod in (
        "modules.whisper.base_transcription_pipeline",
        "modules.whisper.faster_whisper_inference",
        "modules.whisper.whisper_factory",
    ):
        if _mod not in sys.modules:
            sys.modules[_mod] = MagicMock()


_install_whisper_router_stubs()
