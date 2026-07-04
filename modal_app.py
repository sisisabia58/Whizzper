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
        "faster-whisper==1.0.3",
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
        "gradio-i18n"
    )
    .pip_install(
        "git+https://github.com/jhj0517/ultimatevocalremover_api.git",
        "git+https://github.com/jhj0517/pyrubberband.git"
    )
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


@app.function(
    image=whizzper_image,
    gpu="T4",
    timeout=600,
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
    # Set LD_LIBRARY_PATH to include nvidia cublas and cudnn shared objects for CTranslate2
    import os
    cuda_libs = "/usr/local/lib/python3.10/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.10/site-packages/nvidia/cudnn/lib"
    os.environ["LD_LIBRARY_PATH"] = f"{cuda_libs}:{os.environ.get('LD_LIBRARY_PATH', '')}"

    from modules.whisper.faster_whisper_inference import FasterWhisperInference
    from modules.whisper.data_classes import (
        TranscriptionPipelineParams, WhisperParams, VadParams,
        DiarizationParams, BGMSeparationParams
    )

    suffix = os.path.splitext(file_name)[1] if file_name else ".mp3"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(audio_bytes)
        tmp_audio_path = tmp_file.name

    try:
        model_dir = os.path.join(CACHE_DIR, "whisper")
        diar_dir = os.path.join(CACHE_DIR, "diarization")
        uvr_dir = os.path.join(CACHE_DIR, "uvr")
        out_dir = os.path.join(CACHE_DIR, "outputs")

        pipeline = FasterWhisperInference(
            model_dir=model_dir,
            output_dir=out_dir,
            diarization_model_dir=diar_dir,
            uvr_model_dir=uvr_dir
        )

        lang_val = lang
        if lang_val in ("automatic detection", "AUTO", "", "none", "None", "null"):
            lang_val = None

        whisper_p = WhisperParams(
            model_size=model_size or "large-v2",
            lang=lang_val,
            is_translate=bool(is_translate),
            beam_size=beam_size or 5,
            compute_type=compute_type or "float16"
        )
        vad_p = VadParams(vad_filter=str(vad_filter).lower() in ("true", "1"))
        diar_p = DiarizationParams(
            is_diarize=str(is_diarize).lower() in ("true", "1"),
            hf_token=hf_token or os.environ.get("HF_TOKEN", "")
        )
        bgm_p = BGMSeparationParams(is_separate_bgm=str(is_separate_bgm).lower() in ("true", "1"))

        pipeline_params = TranscriptionPipelineParams(
            whisper=whisper_p,
            vad=vad_p,
            diarization=diar_p,
            bgm_separation=bgm_p
        )

        import gradio as gr
        print(f"Running pipeline.run on GPU for {tmp_audio_path} with model {whisper_p.model_size}...", flush=True)
        segments, elapsed_time = pipeline.run(
            tmp_audio_path,
            gr.Progress(),
            "SRT",
            True,
            None,
            *pipeline_params.to_list()
        )
        print(f"Transcription succeeded! Got {len(segments)} segments in {elapsed_time:.2f}s", flush=True)

        formatted_segments = []
        for s in segments:
            words = None
            if hasattr(s, "words") and s.words:
                words = [{"start": w.start, "end": w.end, "word": w.word, "probability": getattr(w, "probability", None)} for w in s.words]
            formatted_segments.append({
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
                "words": words
            })

        return {
            "segments": formatted_segments,
            "elapsed_time": elapsed_time
        }
    except Exception as e:
        tb = traceback.format_exc()
        print(f"Error during Modal GPU inference:\n{tb}", flush=True)
        raise RuntimeError(f"GPU Inference Error: {str(e)}")
    finally:
        if os.path.exists(tmp_audio_path):
            os.remove(tmp_audio_path)


@app.function(
    image=whizzper_image,
    gpu="T4",
    timeout=600,
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
    return run_transcription_gpu.remote(
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
