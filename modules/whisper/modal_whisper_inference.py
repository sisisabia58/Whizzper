import os
import base64
import json
import requests
import time
import tempfile
import subprocess
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
        raw_url = endpoint_url or os.environ.get("MODAL_WEB_ENDPOINT_URL") or "https://revigefarta--whizzper-backend-transcribe-endpoint.modal.run"
        if "," in raw_url:
            self.endpoint_url = raw_url.split(",")[0].strip()
        else:
            self.endpoint_url = raw_url.strip()
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

        if hasattr(audio, "name") and audio.name:
            audio = audio.name
        elif hasattr(audio, "path") and audio.path:
            audio = audio.path
        elif isinstance(audio, dict):
            audio = audio.get("name") or audio.get("path")

        # 1. Read audio file to bytes (compress audio with ffmpeg if video/media file)
        file_name = "audio.mp3"
        tmp_mp3 = None
        if isinstance(audio, str):
            # Compress all audio/video file formats to 64k mono MP3 to guarantee minimal egress
            tmp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp_mp3 = tmp_file.name
            tmp_file.close()
            try:
                cmd = ["ffmpeg", "-y", "-i", audio, "-vn", "-c:a", "libmp3lame", "-b:a", "64k", tmp_mp3]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                read_path = tmp_mp3
                file_name = "audio.mp3"
            except Exception as ex:
                logger.warning(f"ffmpeg compression failed, falling back to raw file: {ex}")
                read_path = audio
                file_name = os.path.basename(audio)

            with open(read_path, "rb") as f:
                audio_bytes = f.read()

            if tmp_mp3 and os.path.exists(tmp_mp3):
                try:
                    os.remove(tmp_mp3)
                except Exception:
                    pass
        elif isinstance(audio, np.ndarray):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
                sf.write(tmp_wav.name, audio, 16000)
                wav_path = tmp_wav.name
            
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_mp3:
                mp3_path = tmp_mp3.name
            
            try:
                cmd = ["ffmpeg", "-y", "-i", wav_path, "-vn", "-c:a", "libmp3lame", "-b:a", "64k", mp3_path]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                with open(mp3_path, "rb") as f:
                    audio_bytes = f.read()
                file_name = "audio.mp3"
            except Exception as ex:
                logger.warning(f"ffmpeg compression from NumPy array failed, falling back: {ex}")
                with open(wav_path, "rb") as f:
                    audio_bytes = f.read()
                file_name = "audio.wav"
            finally:
                if os.path.exists(wav_path):
                    try:
                        os.remove(wav_path)
                    except Exception:
                        pass
                if os.path.exists(mp3_path):
                    try:
                        os.remove(mp3_path)
                    except Exception:
                        pass
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

        def _call_modal():
            # If load balancer endpoints are active, we must target the specific URL via HTTP post
            if os.environ.get("MODAL_ENDPOINTS") or self.endpoint_url:
                logger.info(f"Targeting Modal endpoint via HTTP POST: {self.endpoint_url}")
                json_bytes = json.dumps(payload).encode("utf-8")
                raw_size_mb = len(audio_bytes) / (1024 * 1024)
                payload_size_mb = len(json_bytes) / (1024 * 1024)
                logger.info(f"Uploading audio payload: raw audio = {raw_size_mb:.2f} MB, base64 json = {payload_size_mb:.2f} MB")
                headers = {
                    "Content-Type": "application/json",
                    "Content-Length": str(len(json_bytes))
                }
                response = requests.post(self.endpoint_url, data=json_bytes, headers=headers, timeout=600)
                if response.status_code != 200:
                    raise RuntimeError(f"Modal inference failed [{response.status_code}]: {response.text}")
                return response.json()

            try:
                import modal
                f = modal.Function.from_name("whizzper-backend", "run_transcription_gpu")
                return f.remote(
                    audio_bytes=audio_bytes,
                    file_name=file_name,
                    whisper_type="faster-whisper",
                    model_size=params.whisper.model_size,
                    lang=params.whisper.lang,
                    is_translate=bool(params.whisper.is_translate),
                    beam_size=params.whisper.beam_size,
                    compute_type=params.whisper.compute_type,
                    vad_filter=str(params.vad.vad_filter),
                    is_diarize=str(params.diarization.is_diarize),
                    hf_token=params.diarization.hf_token or os.environ.get("HF_TOKEN", ""),
                    is_separate_bgm=str(params.bgm_separation.is_separate_bgm)
                )
            except Exception as ex:
                logger.info(f"Modal SDK lookup fallback to HTTP endpoint: {ex}")
                json_bytes = json.dumps(payload).encode("utf-8")
                headers = {
                    "Content-Type": "application/json",
                    "Content-Length": str(len(json_bytes))
                }
                response = requests.post(self.endpoint_url, data=json_bytes, headers=headers, timeout=600)
                if response.status_code != 200:
                    raise RuntimeError(f"Modal inference failed [{response.status_code}]: {response.text}")
                return response.json()

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_call_modal)
            p_val = 0.3
            while not future.done():
                try:
                    res_json = future.result(timeout=2.0)
                except concurrent.futures.TimeoutError:
                    elapsed = int(time.time() - start_time)
                    p_val = min(0.95, p_val + 0.01)
                    progress(p_val, desc=f"Processing on Modal GPU server ({elapsed}s elapsed)...")
            res_json = future.result()

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
