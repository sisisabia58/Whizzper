import modal
import os
import io
import base64
import tempfile
import traceback
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import HTTPException, Request

# 1. Define Modal App
app = modal.App("whizzper-backend")

# Persistent volume for caching downloaded models (Faster-Whisper, PyAnnote, UVR)
models_volume = modal.Volume.from_name("whizzper-models-cache", create_if_missing=True)
CACHE_DIR = "/root/.cache/whizzper"

# 2. Define Modal Image with system and python dependencies
whizzper_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("ffmpeg", "git")
    .pip_install("setuptools<70.0.0", "wheel")
    .pip_install(
        "nvidia-cublas-cu12",
        "nvidia-cudnn-cu12",
        "openai-whisper",
        "faster-whisper==1.1.1",
        "torch",
        "torchaudio",
        "ctranslate2",
        "silero-vad",
        "pyannote.audio",
        "soundfile",
        "librosa",
        "scipy",
        "pydantic",
        "fastapi",
        "pyyaml",
        "ruamel.yaml",
        "yt-dlp[default,curl-cffi]",
        "gradio==5.29.0",
        "gradio-i18n==0.3.1",
    )
    .pip_install(
        "git+https://github.com/jhj0517/ultimatevocalremover_api.git",
        "git+https://github.com/jhj0517/pyrubberband.git"
    )
    .env({"PYTHONPATH": "/root"})
    .add_local_dir("modules", remote_path="/root/modules")
    .add_local_dir("configs", remote_path="/root/configs")
)


class TranscriptionRequest(BaseModel):
    audio_base64: str
    file_name: Optional[str] = "audio.wav"
    whisper_type: Optional[str] = "faster-whisper"
    model_size: Optional[str] = "large-v2"
    lang: Optional[str] = None
    is_translate: Optional[bool] = False
    beam_size: Optional[int] = 5
    compute_type: Optional[str] = "float16"
    vad_filter: Optional[str] = "False"
    is_diarize: Optional[str] = "False"
    hf_token: Optional[str] = ""
    is_separate_bgm: Optional[str] = "False"
    extra_params: Optional[Dict[str, Any]] = None

# Globally cache the pipeline instance in the container scope to avoid re-instantiation overhead on warm reuse.
_pipeline_cache = {}

def get_pipeline():
    global _pipeline_cache
    if "pipeline" not in _pipeline_cache:
        from modules.whisper.faster_whisper_inference import FasterWhisperInference
        model_dir = os.path.join(CACHE_DIR, "whisper")
        diar_dir = os.path.join(CACHE_DIR, "diarization")
        uvr_dir = os.path.join(CACHE_DIR, "uvr")
        out_dir = os.path.join(CACHE_DIR, "outputs")
        _pipeline_cache["pipeline"] = FasterWhisperInference(
            model_dir=model_dir,
            output_dir=out_dir,
            diarization_model_dir=diar_dir,
            uvr_model_dir=uvr_dir
        )
    return _pipeline_cache["pipeline"]


def _format_segment(s: Any) -> Dict[str, Any]:
    words = None
    if hasattr(s, "words") and s.words:
        words = [
            {
                "start": w.start,
                "end": w.end,
                "word": w.word,
                "probability": getattr(w, "probability", None),
            }
            for w in s.words
        ]
    return {
        "id": getattr(s, "id", None),
        "seek": getattr(s, "seek", None),
        "text": getattr(s, "text", None),
        "start": getattr(s, "start", None),
        "end": getattr(s, "end", None),
        "tokens": getattr(s, "tokens", None),
        "temperature": getattr(s, "temperature", None),
        "avg_logprob": getattr(s, "avg_logprob", None),
        "compression_ratio": getattr(s, "compression_ratio", None),
        "no_speech_prob": getattr(s, "no_speech_prob", None),
        "words": words,
    }


def _transcribe_direct(
    tmp_audio_path: str,
    model_size: str,
    lang: Optional[str],
    is_translate: bool,
    beam_size: int,
    compute_type: str,
    vad_filter: bool,
) -> Dict[str, Any]:
    """faster-whisper only — no Gradio / UVR / pyannote import graph."""
    import time
    import torch
    import faster_whisper

    cuda_libs = "/usr/local/lib/python3.10/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.10/site-packages/nvidia/cudnn/lib"
    os.environ["LD_LIBRARY_PATH"] = f"{cuda_libs}:{os.environ.get('LD_LIBRARY_PATH', '')}"

    device = "cuda" if torch.cuda.is_available() else "cpu"
    ct = compute_type or "float16"
    if device == "cpu" and ct in ("float16", "int8_float16"):
        ct = "int8"
    print(
        f"direct whisper model={model_size} device={device} compute_type={ct} cuda={torch.cuda.is_available()}",
        flush=True,
    )

    model_dir = os.path.join(CACHE_DIR, "whisper")
    os.makedirs(model_dir, exist_ok=True)
    cache_key = f"{model_size}:{device}:{ct}"
    model = _pipeline_cache.get(cache_key)
    if model is None:
        model = faster_whisper.WhisperModel(
            model_size,
            device=device,
            compute_type=ct,
            download_root=model_dir,
        )
        _pipeline_cache[cache_key] = model

    start = time.time()
    segments_iter, _info = model.transcribe(
        tmp_audio_path,
        language=lang,
        task="translate" if is_translate else "transcribe",
        beam_size=beam_size or 5,
        vad_filter=vad_filter,
        word_timestamps=True,
    )
    formatted = [_format_segment(s) for s in segments_iter]
    elapsed = time.time() - start
    print(f"direct whisper done segments={len(formatted)} elapsed={elapsed:.2f}s", flush=True)
    return {"segments": formatted, "elapsed_time": elapsed}


@app.function(
    image=whizzper_image,
    gpu=["T4", "L4", "A10", "any"],
    timeout=600,
    max_containers=10,
    volumes={CACHE_DIR: models_volume},
    secrets=[modal.Secret.from_name("whizzper-secrets")] if os.environ.get("USE_MODAL_SECRET") else []
)
def run_transcription_gpu(
    audio_bytes: bytes,
    file_name: str = "audio.wav",
    whisper_type: str = "faster-whisper",
    model_size: str = "large-v2",
    lang: Optional[str] = None,
    is_translate: bool = False,
    beam_size: int = 5,
    compute_type: str = "float16",
    vad_filter: str = "False",
    is_diarize: str = "False",
    hf_token: str = "",
    is_separate_bgm: str = "False"
) -> Dict[str, Any]:
    """
    Direct Modal function for GPU transcription (bypasses HTTP limits via binary gRPC stream).
    """
    lang_val = lang
    if lang_val in ("automatic detection", "AUTO", "", "none", "None", "null"):
        lang_val = None
    want_diarize = str(is_diarize).lower() in ("true", "1")
    want_bgm = str(is_separate_bgm).lower() in ("true", "1")
    want_vad = str(vad_filter).lower() in ("true", "1")

    suffix = os.path.splitext(file_name)[1] if file_name else ".mp3"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(audio_bytes)
        tmp_audio_path = tmp_file.name

    try:
        if not want_diarize and not want_bgm:
            return _transcribe_direct(
                tmp_audio_path=tmp_audio_path,
                model_size=model_size or "large-v2",
                lang=lang_val,
                is_translate=bool(is_translate),
                beam_size=beam_size or 5,
                compute_type=compute_type or "float16",
                vad_filter=want_vad,
            )

        cuda_libs = "/usr/local/lib/python3.10/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.10/site-packages/nvidia/cudnn/lib"
        os.environ["LD_LIBRARY_PATH"] = f"{cuda_libs}:{os.environ.get('LD_LIBRARY_PATH', '')}"

        from modules.whisper.data_classes import (
            TranscriptionPipelineParams, WhisperParams, VadParams,
            DiarizationParams, BGMSeparationParams
        )

        pipeline = get_pipeline()
        pipeline_params = TranscriptionPipelineParams(
            whisper=WhisperParams(
                model_size=model_size or "large-v2",
                lang=lang_val,
                is_translate=bool(is_translate),
                beam_size=beam_size or 5,
                compute_type=compute_type or "float16",
            ),
            vad=VadParams(vad_filter=want_vad),
            diarization=DiarizationParams(
                is_diarize=want_diarize,
                hf_token=hf_token or os.environ.get("HF_TOKEN", ""),
            ),
            bgm_separation=BGMSeparationParams(is_separate_bgm=want_bgm),
        )

        class _NoOpProgress:
            def __call__(self, *args, **kwargs):
                return None

        print(f"Running pipeline.run on GPU for {tmp_audio_path} with model {model_size}...", flush=True)
        segments, elapsed_time = pipeline.run(
            tmp_audio_path,
            _NoOpProgress(),
            "SRT",
            True,
            None,
            *pipeline_params.to_list()
        )
        print(f"Transcription succeeded! Got {len(segments)} segments in {elapsed_time:.2f}s", flush=True)
        return {
            "segments": [_format_segment(s) for s in segments],
            "elapsed_time": elapsed_time,
        }
    except Exception as e:
        tb = traceback.format_exc()
        print(f"Error during Modal GPU inference:\n{tb}", flush=True)
        raise RuntimeError(f"GPU Inference Error: {type(e).__name__}: {e}") from e
    finally:
        if os.path.exists(tmp_audio_path):
            os.remove(tmp_audio_path)


@app.function(
    image=whizzper_image,
    timeout=600,
    max_containers=10,
    volumes={CACHE_DIR: models_volume},
    secrets=[modal.Secret.from_name("whizzper-secrets")] if os.environ.get("USE_MODAL_SECRET") else []
)
@modal.fastapi_endpoint(method="POST")
async def transcribe_endpoint(request: Request) -> Dict[str, Any]:
    """
    Web endpoint for running Whisper transcription on GPU via Modal.
    """
    try:
        data = await request.json()
        req = TranscriptionRequest(**data)
    except Exception as ex:
        tb = traceback.format_exc()
        print(f"Failed to parse request JSON / Pydantic validation: {tb}", flush=True)
        raise HTTPException(status_code=400, detail=f"Bad Request: {str(ex)}")

    audio_bytes = base64.b64decode(req.audio_base64)
    try:
        return await run_transcription_gpu.remote.aio(
            audio_bytes=audio_bytes,
            file_name=req.file_name or "audio.wav",
            whisper_type=req.whisper_type or "faster-whisper",
            model_size=req.model_size or "large-v2",
            lang=req.lang,
            is_translate=bool(req.is_translate),
            beam_size=req.beam_size or 5,
            compute_type=req.compute_type or "float16",
            vad_filter=req.vad_filter or "False",
            is_diarize=req.is_diarize or "False",
            hf_token=req.hf_token or "",
            is_separate_bgm=req.is_separate_bgm or "False"
        )
    except Exception as e:
        tb = traceback.format_exc()
        print(f"Modal GPU remote failed:\n{tb}", flush=True)
        raise HTTPException(
            status_code=500,
            detail=f"GPU Inference Error: {type(e).__name__}: {e}",
        ) from e
