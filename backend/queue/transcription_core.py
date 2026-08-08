"""Shared transcription execution logic for API and Celery workers."""
import os
import threading
import time
import wave
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from modules.utils.paths import BACKEND_CACHE_DIR
from backend.queue.audio_paths import wav_path_for_task, wav_exists
from modules.whisper.data_classes import (
    BGMSeparationParams,
    DiarizationParams,
    TranscriptionPipelineParams,
    VadParams,
    WhisperParams,
)
from backend.common.progress import NO_OP_PROGRESS
from backend.db.task.dao import update_task_status_in_db
from backend.db.task.models import TaskStatus


def load_audio_from_wav(wav_path: str) -> Tuple[np.ndarray, float]:
    with wave.open(wav_path, "rb") as w:
        frames = w.readframes(w.getnframes())
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        duration = w.getnframes() / w.getframerate()
    return audio, duration


def save_audio_to_wav(task_uuid: str, audio: np.ndarray, sample_rate: int = 16000) -> str:
    path = wav_path_for_task(task_uuid)
    os.makedirs(os.path.dirname(path) or BACKEND_CACHE_DIR, exist_ok=True)
    pcm = np.clip(audio, -1.0, 1.0)
    pcm16 = (pcm * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm16.tobytes())
    return path


def params_from_task_dict(task_params: dict) -> TranscriptionPipelineParams:
    whisper_d = task_params.get("whisper_params", task_params.get("whisper", {}))
    vad_d = task_params.get("vad_params", task_params.get("vad", {}))
    bgm_d = task_params.get("bgm_separation_params", task_params.get("bgm_separation", {}))
    diar_d = task_params.get("diarization_params", task_params.get("diarization", {}))
    return TranscriptionPipelineParams(
        whisper=WhisperParams(**whisper_d),
        vad=VadParams(**vad_d),
        bgm_separation=BGMSeparationParams(**bgm_d),
        diarization=DiarizationParams(**diar_d),
    )


def get_drive_manager(task_params: dict, session):
    from modules.utils.drive_manager import DriveManager

    if task_params.get("access_mode") == "connect":
        from backend.db.drive.dao import get_connection_from_db
        from modules.utils.drive_auth import decrypt_token

        conn_id = task_params.get("connection_id")
        conn = get_connection_from_db(session, conn_id)
        if conn:
            creds_dict = {
                "token": decrypt_token(conn.access_token_enc),
                "refresh_token": decrypt_token(conn.refresh_token_enc),
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": os.environ.get("GOOGLE_OAUTH_CLIENT_ID"),
                "client_secret": os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET"),
            }
            return DriveManager(credentials_dict=creds_dict)
    return DriveManager()


def run_writeback(session, task, task_params: dict, segments: List[dict]) -> None:
    writeback_opt = task_params.get("writeback", {})
    if task_params.get("access_mode") != "connect" or not writeback_opt.get("enabled", True):
        return
    if not task.source_parent_id:
        return

    try:
        from backend.common.zip_writer import compile_srt

        manager = get_drive_manager(task_params, session)
        srt_text = compile_srt(segments)
        srt_name = f"{os.path.splitext(task.file_name)[0]}.srt"
        file_id = manager.upload_srt(
            filename=srt_name,
            srt_content=srt_text,
            parent_id=task.source_parent_id,
            on_conflict=writeback_opt.get("on_conflict", "version"),
        )
        if file_id:
            task.writeback_status = "UPLOADED"
            task.writeback_file_id = file_id
        else:
            task.writeback_status = "SKIPPED"
    except Exception as wb_err:
        task.writeback_status = "FAILED"
        task.writeback_error = str(wb_err)


def run_transcription_inference(
    identifier: str,
    audio: np.ndarray,
    params: TranscriptionPipelineParams,
    progress_callback=None,
) -> Tuple[List[Any], float]:
    from backend.routers.transcription.router import (
        get_pipeline,
        modal_pool,
        max_retries_pool,
        create_progress_callback,
    )

    is_modal = bool(os.environ.get("MODAL_WEB_ENDPOINT_URL") or os.environ.get("MODAL_ENDPOINTS"))
    stop_progress_event = threading.Event()
    progress_thread = None

    def simulate_progress():
        current_progress = 0.05
        while not stop_progress_event.is_set() and current_progress < 0.92:
            time.sleep(1.5)
            if stop_progress_event.is_set():
                break
            current_progress += 0.04
            current_progress = min(current_progress, 0.92)
            try:
                update_task_status_in_db(
                    identifier=identifier,
                    update_data={
                        "uuid": identifier,
                        "status": TaskStatus.IN_PROGRESS,
                        "progress": round(current_progress, 2),
                        "updated_at": datetime.utcnow(),
                    },
                )
            except Exception:
                pass

    if is_modal:
        progress_thread = threading.Thread(target=simulate_progress, daemon=True)
        progress_thread.start()

    cb = progress_callback
    if cb is None and not is_modal:
        cb = create_progress_callback(identifier)
    try:
        if not is_modal or not modal_pool:
            segments, elapsed_time = get_pipeline().run(
                audio,
                NO_OP_PROGRESS,
                "SRT",
                False,
                cb,
                *params.to_list(),
            )
        else:
            last_err = None
            success = False
            for _attempt in range(max_retries_pool + 1):
                try:
                    with modal_pool.acquire() as ep:
                        try:
                            segments, elapsed_time = get_pipeline(endpoint_url=ep).run(
                                audio,
                                NO_OP_PROGRESS,
                                "SRT",
                                False,
                                None,
                                *params.to_list(),
                            )
                            modal_pool.record_success(ep)
                            success = True
                            break
                        except Exception as trans_err:
                            modal_pool.record_failure(ep)
                            raise trans_err
                except Exception as e:
                    last_err = e
                    if "capacity limit exceeded" in str(e) or "No healthy endpoints" in str(e):
                        time.sleep(0.5)
            if not success:
                raise last_err or RuntimeError("Modal execution failed on all retries")
    finally:
        if progress_thread:
            stop_progress_event.set()
            progress_thread.join(timeout=1.0)

    return segments, elapsed_time


def execute_transcription_for_identifier(
    identifier: str,
    audio: np.ndarray,
    params: TranscriptionPipelineParams,
) -> Dict[str, Any]:
    update_task_status_in_db(
        identifier=identifier,
        update_data={
            "uuid": identifier,
            "status": TaskStatus.IN_PROGRESS,
            "progress": 0.05,
            "updated_at": datetime.utcnow(),
        },
    )
    segments, elapsed_time = run_transcription_inference(identifier, audio, params)
    segment_dicts = [seg.model_dump() for seg in segments]
    update_task_status_in_db(
        identifier=identifier,
        update_data={
            "uuid": identifier,
            "status": TaskStatus.COMPLETED,
            "result": segment_dicts,
            "updated_at": datetime.utcnow(),
            "duration": elapsed_time,
            "progress": 1.0,
        },
    )
    return {"status": "completed", "uuid": identifier, "segments": segment_dicts}
