import subprocess
from io import BytesIO
import numpy as np
import httpx
from pydantic import BaseModel
from fastapi import (
    HTTPException,
    UploadFile,
)
from typing import Annotated, Any, BinaryIO, Literal, Generator, Union, Optional, List, Tuple


class AudioInfo(BaseModel):
    duration: float


def decode_audio_bytes(file_content: bytes) -> np.ndarray:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-i",
            "pipe:0",
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ac",
            "1",
            "-ar",
            "16000",
            "pipe:1",
        ],
        input=file_content,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise HTTPException(status_code=422, detail="Could not decode audio")
    audio = np.frombuffer(proc.stdout, dtype=np.float32)
    return audio


async def read_audio(
    file: Optional[UploadFile] = None,
    file_url: Optional[str] = None
):
    """Read audio from "UploadFile". This resamples sampling rates to 16000."""
    if (file and file_url) or (not file and not file_url):
        raise HTTPException(status_code=400, detail="Provide only one of file or file_url")

    if file:
        file_content = await file.read()
    elif file_url:
        async with httpx.AsyncClient() as client:
            file_response = await client.get(file_url)
        if file_response.status_code != 200:
            raise HTTPException(status_code=422, detail="Could not download the file")
        file_content = file_response.content
    audio = decode_audio_bytes(file_content)
    duration = len(audio) / 16000
    return audio, AudioInfo(duration=duration)
