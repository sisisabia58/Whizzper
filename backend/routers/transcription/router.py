import functools
import uuid
import numpy as np
from fastapi import (
    File,
    UploadFile,
)
import gradio as gr
from fastapi import APIRouter, BackgroundTasks, Depends, Response, status, Body
from typing import List, Dict
from sqlalchemy.orm import Session
from datetime import datetime
from modules.whisper.data_classes import *
from modules.utils.paths import BACKEND_CACHE_DIR
from modules.whisper.faster_whisper_inference import FasterWhisperInference
from modules.whisper.base_transcription_pipeline import BaseTranscriptionPipeline
from backend.common.audio import read_audio
from backend.common.models import QueueResponse
from backend.common.config_loader import load_server_config
from backend.db.task.dao import (
    add_task_to_db,
    get_db_session,
    update_task_status_in_db
)
from backend.db.task.models import TaskStatus, TaskType

transcription_router = APIRouter(prefix="/transcription", tags=["Transcription"])


def create_progress_callback(identifier: str):
    def progress_callback(progress_value: float):
        update_task_status_in_db(
            identifier=identifier,
            update_data={
                "uuid": identifier,
                "status": TaskStatus.IN_PROGRESS,
                "progress": round(progress_value, 2),
                "updated_at": datetime.utcnow()
            },
        )
    return progress_callback


@functools.lru_cache
def get_pipeline() -> 'BaseTranscriptionPipeline':
    import os
    from modules.whisper.whisper_factory import WhisperFactory
    config = load_server_config()["whisper"]
    
    # Use WhisperFactory to automatically switch to Modal serverless inference
    # when MODAL_WEB_ENDPOINT_URL is configured.
    inferencer = WhisperFactory.create_whisper_inference(
        whisper_type="faster-whisper",
        output_dir=BACKEND_CACHE_DIR
    )
    
    # If we are not running on Modal, initialize/update local model settings
    if not os.environ.get("MODAL_WEB_ENDPOINT_URL"):
        inferencer.update_model(
            model_size=config["model_size"],
            compute_type=config["compute_type"]
        )
    return inferencer


def run_transcription(
    audio: np.ndarray,
    params: TranscriptionPipelineParams,
    identifier: str,
) -> List[Segment]:
    import threading
    import time
    import os

    update_task_status_in_db(
        identifier=identifier,
        update_data={
            "uuid": identifier,
            "status": TaskStatus.IN_PROGRESS,
            "progress": 0.05,
            "updated_at": datetime.utcnow()
        },
    )

    stop_progress_event = threading.Event()

    def simulate_progress():
        # Incremental loader for Modal serverless GPU execution
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
                        "updated_at": datetime.utcnow()
                    },
                )
            except Exception:
                pass

    is_modal = bool(os.environ.get("MODAL_WEB_ENDPOINT_URL"))
    progress_thread = None
    if is_modal:
        progress_thread = threading.Thread(target=simulate_progress, daemon=True)
        progress_thread.start()

    progress_callback = create_progress_callback(identifier)
    try:
        segments, elapsed_time = get_pipeline().run(
            audio,
            gr.Progress(),
            "SRT",
            False,
            progress_callback if not is_modal else None,  
            *params.to_list()
        )
    finally:
        if progress_thread:
            stop_progress_event.set()
            progress_thread.join(timeout=1.0)

    segments = [seg.model_dump() for seg in segments]

    update_task_status_in_db(
        identifier=identifier,
        update_data={
            "uuid": identifier,
            "status": TaskStatus.COMPLETED,
            "result": segments,
            "updated_at": datetime.utcnow(),
            "duration": elapsed_time,
            "progress": 1.0,
        },
    )
    return segments


@transcription_router.post(
    "/",
    response_model=QueueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Transcribe Audio",
    description="Process the provided audio or video file to generate a transcription.",
)
async def transcription(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Audio or video file to transcribe."),
    whisper_params: WhisperParams = Depends(),
    vad_params: VadParams = Depends(),
    bgm_separation_params: BGMSeparationParams = Depends(),
    diarization_params: DiarizationParams = Depends(),
) -> QueueResponse:
    if not isinstance(file, np.ndarray):
        audio, info = await read_audio(file=file)
    else:
        audio, info = file, None

    params = TranscriptionPipelineParams(
        whisper=whisper_params,
        vad=vad_params,
        bgm_separation=bgm_separation_params,
        diarization=diarization_params
    )

    identifier = add_task_to_db(
        status=TaskStatus.QUEUED,
        file_name=file.filename,
        audio_duration=info.duration if info else None,
        language=params.whisper.lang,
        task_type=TaskType.TRANSCRIPTION,
        task_params=params.to_dict(),
    )

    background_tasks.add_task(
        run_transcription,
        audio=audio,
        params=params,
        identifier=identifier,
    )

    return QueueResponse(identifier=identifier, status=TaskStatus.QUEUED, message="Transcription task has queued")


@transcription_router.post("/batch", status_code=201)
async def queue_batch_transcription(
    background_tasks: BackgroundTasks,
    payload: dict = Body(...),
    session: Session = Depends(get_db_session)
):
    import uuid
    from backend.db.batch.dao import add_batch_to_db
    from backend.db.task.models import Task, TaskStatus, TaskType

    batch_id = str(uuid.uuid4())
    selected_ids = payload.get("selected_file_ids", [])
    folder_name = payload.get("folder_name", "Batch Job")
    folder_url = payload.get("folder_url", "")
    
    # Create Batch Parent
    add_batch_to_db(
        session=session,
        batch_id=batch_id,
        folder_name=folder_name,
        source_url=folder_url,
        total_files=len(selected_ids),
        task_params=payload
    )
    
    # Queue each child file
    for file_id in selected_ids:
        # Create Child Task
        add_task_to_db(
            session=session,
            status=TaskStatus.QUEUED,
            file_name=f"Drive_File_{file_id}",
            task_type=TaskType.TRANSCRIPTION,
            task_params=payload,
            batch_id=batch_id,
            source_file_id=file_id
        )
        
    background_tasks.add_task(
        run_batch_dispatcher,
        batch_id=batch_id,
        selected_ids=selected_ids,
        task_params=payload
    )
    
    return {
        "batch_id": batch_id,
        "status": "queued",
        "total_files": len(selected_ids),
        "message": "Batch transcription queued"
    }


async def run_batch_dispatcher(batch_id: str, selected_ids: list, task_params: dict):
    import os
    import asyncio
    import threading
    import time
    from backend.db.task.models import Task, TaskStatus
    from backend.db.batch.dao import update_batch_rollup
    from modules.utils.drive_manager import DriveManager
    from backend.db.db_instance import get_db_session

    concurrency_limit = int(os.environ.get("BATCH_MAX_CONCURRENCY", "8"))
    sem = asyncio.Semaphore(concurrency_limit)
    
    async def process_child(file_id: str):
        async with sem:
            # We open a new database session in this thread/coroutine to be fully thread-safe
            session = next(get_db_session())
            task = session.query(Task).filter(Task.batch_id == batch_id, Task.source_file_id == file_id).first()
            if not task:
                session.close()
                return
                
            task.status = TaskStatus.IN_PROGRESS
            task.progress = 0.05
            task.updated_at = datetime.utcnow()
            session.commit()
            
            # Simulate progress in a background thread for Modal execution
            stop_progress_event = threading.Event()
            
            def simulate_child_progress():
                current_progress = 0.05
                while not stop_progress_event.is_set() and current_progress < 0.92:
                    time.sleep(1.5)
                    if stop_progress_event.is_set():
                        break
                    current_progress += 0.04
                    current_progress = min(current_progress, 0.92)
                    try:
                        # Open new session for safety in daemon thread
                        progress_session = next(get_db_session())
                        t = progress_session.query(Task).filter(Task.uuid == task.uuid).first()
                        if t:
                            t.progress = round(current_progress, 2)
                            t.updated_at = datetime.utcnow()
                            progress_session.commit()
                        progress_session.close()
                    except Exception:
                        pass
                        
            is_modal = bool(os.environ.get("MODAL_WEB_ENDPOINT_URL"))
            progress_thread = None
            if is_modal:
                progress_thread = threading.Thread(target=simulate_child_progress, daemon=True)
                progress_thread.start()
            
            wav_path = os.path.join(BACKEND_CACHE_DIR, f"{task.uuid}.wav")
            try:
                # 1. Download & Extract
                manager = DriveManager()
                manager.download_and_extract_audio(file_id, wav_path)
                
                import wave
                with wave.open(wav_path, "rb") as w:
                    frames = w.readframes(w.getnframes())
                    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                    duration = w.getnframes() / w.getframerate()
                task.audio_duration = duration
                session.commit()

                
                # Parse shared task parameters
                whisper_d = task_params.get("whisper_params", {})
                vad_d = task_params.get("vad_params", {})
                bgm_d = task_params.get("bgm_separation_params", {})
                diar_d = task_params.get("diarization_params", {})
                
                params = TranscriptionPipelineParams(
                    whisper=WhisperParams(**whisper_d),
                    vad=VadParams(**vad_d),
                    bgm_separation=BGMSeparationParams(**bgm_d),
                    diarization=DiarizationParams(**diar_d)
                )
                
                segments, elapsed_time = get_pipeline().run(
                    audio,
                    gr.Progress(),
                    "SRT",
                    False,
                    None,
                    *params.to_list()
                )
                segments = [seg.model_dump() for seg in segments]
                
                if progress_thread:
                    stop_progress_event.set()
                    progress_thread.join(timeout=1.0)
                
                task.status = TaskStatus.COMPLETED
                task.result = segments
                task.duration = elapsed_time
                task.progress = 1.0
                task.updated_at = datetime.utcnow()
            except Exception as err:
                if progress_thread:
                    stop_progress_event.set()
                    progress_thread.join(timeout=1.0)
                task.status = TaskStatus.FAILED
                task.error = str(err)
                task.updated_at = datetime.utcnow()
            finally:
                if os.path.exists(wav_path):
                    try:
                        os.remove(wav_path)
                    except Exception:
                        pass
                session.commit()
                # Update parent rollup
                update_batch_rollup(batch_id, session)
                session.close()
                
    await asyncio.gather(*(process_child(fid) for fid in selected_ids))



