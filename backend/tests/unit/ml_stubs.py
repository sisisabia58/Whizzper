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
    if find_spec(name) is not None:
        return
    mod = types.ModuleType(name)
    mod.__spec__ = ModuleSpec(name, None)
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

for _name in [
    "modules.whisper.faster_whisper_inference",
    "modules.vad.silero_vad_inference",
    "modules.uvr.music_separator",
    "modules.diarize.diarizer",
]:
    if _name not in sys.modules:
        sys.modules[_name] = MagicMock()
