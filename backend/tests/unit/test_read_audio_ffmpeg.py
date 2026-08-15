import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi import UploadFile


def test_audio_module_does_not_import_faster_whisper():
    tree = ast.parse(Path("backend/common/audio.py").read_text())
    roots = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert "faster_whisper" not in roots


@pytest.mark.asyncio
async def test_read_audio_uses_ffmpeg(tmp_path, monkeypatch):
    from backend.common.audio import read_audio

    pcm = (np.zeros(16000, dtype=np.float32)).tobytes()

    class FakeProc:
        def __init__(self):
            self.stdout = pcm
            self.returncode = 0
            self.stderr = b""

    upload = MagicMock(spec=UploadFile)
    upload.read = MagicMock(return_value=b"fake-bytes")

    async def _read():
        return b"fake-bytes"

    upload.read = _read

    with patch("backend.common.audio.subprocess.run", return_value=FakeProc()):
        audio, info = await read_audio(file=upload)
    assert audio.dtype == np.float32
    assert info.duration == pytest.approx(1.0)
