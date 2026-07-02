import os
import base64
import requests
import time
import tempfile
import soundfile as sf
from typing import Union, BinaryIO, Tuple, List, Optional, Callable
import numpy as np
import gradio as gr

from modules.whisper.base_transcription_pipeline import BaseTranscriptionPipeline
from modules.whisper.data_classes import Segment, Word, TranscriptionPipelineParams, WhisperParams
from modules.utils.logger import get_logger

logger = get_logger()


class ModalWhisperInference(BaseTranscriptionPipeline):
    """
    Transcription pipeline implementation that delegates GPU inference to Modal serverless endpoint.
    """
    def __init__(self,
                 endpoint_url: Optional[str] = None,
                 output_dir: str = "outputs",
                 **kwargs):
        super().__init__(output_dir=output_dir)
        self.endpoint_url = endpoint_url or os.environ.get("MODAL_WEB_ENDPOINT_URL", "")
        self.device = "modal-gpu"
        self.available_models = ["tiny", "base", "small", "medium", "large", "large-v1", "large-v2", "large-v3"]
        self.available_compute_types = ["float16", "int8", "float32"]

    def update_model(self,
                     model_size: str,
                     compute_type: str,
                     progress: gr.Progress = gr.Progress()):
        self.current_model_size = model_size
        self.current_compute_type = compute_type
        logger.info(f"Modal pipeline set to model: {model_size}, compute_type: {compute_type}")

    def transcribe(self,
                   audio: Union[str, BinaryIO, np.ndarray],
                   progress: gr.Progress = gr.Progress(),
                   progress_callback: Optional[Callable] = None,
                   *whisper_params) -> Tuple[List[Segment], float]:
        """Direct transcribe call fallback"""
        params = WhisperParams.from_list(list(whisper_params))
        pipeline_params = TranscriptionPipelineParams(whisper=params)
        return self.run(audio, progress, "SRT", True, progress_callback, *pipeline_params.to_list())

    def run(self,
            audio: Union[str, BinaryIO, np.ndarray],
            progress: gr.Progress = gr.Progress(),
            file_format: str = "SRT",
            add_timestamp: bool = True,
            progress_callback: Optional[Callable] = None,
            *pipeline_params) -> Tuple[List[Segment], float]:
        """
        Send audio payload to Modal endpoint for remote GPU inference.
        """
        if not self.endpoint_url:
            raise ValueError(
                "Modal endpoint URL is not configured. Please set MODAL_WEB_ENDPOINT_URL environment variable."
            )

        progress(0.1, desc="Preparing audio for Modal GPU server...")

        # 1. Read audio file to bytes
        file_name = "audio.wav"
        if isinstance(audio, str):
            file_name = os.path.basename(audio)
            with open(audio, "rb") as f:
                audio_bytes = f.read()
        elif isinstance(audio, np.ndarray):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                sf.write(tmp.name, audio, 16000)
                tmp_path = tmp.name
            with open(tmp_path, "rb") as f:
                audio_bytes = f.read()
            os.remove(tmp_path)
        else:
            audio_bytes = audio.read()

        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        # 2. Parse parameters
        params = TranscriptionPipelineParams.from_list(list(pipeline_params))
        params = self.validate_gradio_values(params)

        payload = {
            "audio_base64": audio_b64,
            "file_name": file_name,
            "whisper_type": "faster-whisper",
            "model_size": params.whisper.model_size,
            "lang": params.whisper.lang,
            "is_translate": params.whisper.is_translate,
            "beam_size": params.whisper.beam_size,
            "compute_type": params.whisper.compute_type,
            "vad_filter": str(params.vad.vad_filter),
            "is_diarize": str(params.diarization.is_diarize),
            "hf_token": params.diarization.hf_token or os.environ.get("HF_TOKEN", ""),
            "is_separate_bgm": str(params.bgm_separation.is_separate_bgm)
        }

        progress(0.3, desc="Offloading inference to Modal GPU...")
        start_time = time.time()

        response = requests.post(self.endpoint_url, json=payload, timeout=600)
        if response.status_code != 200:
            raise RuntimeError(f"Modal inference failed [{response.status_code}]: {response.text}")

        res_json = response.json()
        segments_raw = res_json.get("segments", [])
        elapsed_time = res_json.get("elapsed_time", time.time() - start_time)

        # 3. Reconstruct Segment objects
        segments = []
        for s in segments_raw:
            words = None
            if s.get("words"):
                words = [Word(start=w["start"], end=w["end"], word=w["word"], probability=w.get("probability")) for w in s["words"]]
            segments.append(Segment(
                id=s.get("id"),
                seek=s.get("seek"),
                text=s.get("text"),
                start=s.get("start"),
                end=s.get("end"),
                tokens=s.get("tokens"),
                temperature=s.get("temperature"),
                avg_logprob=s.get("avg_logprob"),
                compression_ratio=s.get("compression_ratio"),
                no_speech_prob=s.get("no_speech_prob"),
                words=words
            ))

        progress(1.0, desc="Finished Modal inference.")
        return segments, elapsed_time
