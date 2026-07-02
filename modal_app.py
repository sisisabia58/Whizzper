import modal
import os
import io
import base64
import tempfile
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

# 1. Define Modal App
app = modal.App("whizzper-backend")

# Persistent volume for caching downloaded models (Faster-Whisper, PyAnnote, UVR)
models_volume = modal.Volume.from_name("whizzper-models-cache", create_if_missing=True)
CACHE_DIR = "/root/.cache/whizzper"

# 2. Define Modal Image with system and python dependencies
whizzper_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("ffmpeg", "git")
    .pip_install(
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
        "gradio-i18n"
    )
    .add_local_python_source("modules")
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
    vad_filter: Optional[str] = "False"  # String representation or bool
    is_diarize: Optional[str] = "False"
    hf_token: Optional[str] = ""
    is_separate_bgm: Optional[str] = "False"
    extra_params: Optional[Dict[str, Any]] = None


class WordDTO(BaseModel):
    start: Optional[float] = None
    end: Optional[float] = None
    word: Optional[str] = None
    probability: Optional[float] = None


class SegmentDTO(BaseModel):
    id: Optional[int] = None
    seek: Optional[int] = None
    text: Optional[str] = None
    start: Optional[float] = None
    end: Optional[float] = None
    tokens: Optional[List[int]] = None
    temperature: Optional[float] = None
    avg_logprob: Optional[float] = None
    compression_ratio: Optional[float] = None
    no_speech_prob: Optional[float] = None
    words: Optional[List[WordDTO]] = None


class TranscriptionResponse(BaseModel):
    segments: List[SegmentDTO]
    elapsed_time: float


@app.function(
    image=whizzper_image,
    gpu="T4",
    timeout=600,
    volumes={CACHE_DIR: models_volume},
    secrets=[modal.Secret.from_name("whizzper-secrets")] if os.environ.get("USE_MODAL_SECRET") else []
)
@modal.fastapi_endpoint(method="POST")
def transcribe_endpoint(req: TranscriptionRequest) -> Dict[str, Any]:
    """
    Web endpoint for running Whisper transcription on GPU via Modal.
    """
    from modules.whisper.whisper_factory import WhisperFactory
    from modules.whisper.data_classes import (
        TranscriptionPipelineParams, WhisperParams, VadParams,
        DiarizationParams, BGMSeparationParams
    )

    # 1. Decode audio bytes and save to temporary file
    audio_bytes = base64.b64decode(req.audio_base64)
    suffix = os.path.splitext(req.file_name)[1] if req.file_name else ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(audio_bytes)
        tmp_audio_path = tmp_file.name

    try:
        # 2. Configure model directories to persistent volume
        model_dir = os.path.join(CACHE_DIR, "whisper")
        diar_dir = os.path.join(CACHE_DIR, "diarization")
        uvr_dir = os.path.join(CACHE_DIR, "uvr")
        out_dir = os.path.join(CACHE_DIR, "outputs")

        # 3. Create pipeline instance
        pipeline = WhisperFactory.create_whisper_inference(
            whisper_type=req.whisper_type or "faster-whisper",
            faster_whisper_model_dir=model_dir,
            diarization_model_dir=diar_dir,
            uvr_model_dir=uvr_dir,
            output_dir=out_dir
        )

        # 4. Construct pipeline params
        whisper_p = WhisperParams(
            model_size=req.model_size or "large-v2",
            lang=req.lang,
            is_translate=bool(req.is_translate),
            beam_size=req.beam_size or 5,
            compute_type=req.compute_type or "float16"
        )
        vad_p = VadParams(vad_filter=str(req.vad_filter).lower() in ("true", "1"))
        diar_p = DiarizationParams(
            is_diarize=str(req.is_diarize).lower() in ("true", "1"),
            hf_token=req.hf_token or os.environ.get("HF_TOKEN", "")
        )
        bgm_p = BGMSeparationParams(is_separate_bgm=str(req.is_separate_bgm).lower() in ("true", "1"))

        pipeline_params = TranscriptionPipelineParams(
            whisper=whisper_p,
            vad=vad_p,
            diarization=diar_p,
            bgm_separation=bgm_p
        )

        # 5. Execute transcription pipeline on GPU
        segments, elapsed_time = pipeline.run(
            tmp_audio_path,
            *pipeline_params.to_list()
        )

        # 6. Format result for JSON response
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
    finally:
        if os.path.exists(tmp_audio_path):
            os.remove(tmp_audio_path)
