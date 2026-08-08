import functools
import os
import uuid
import numpy as np
from fastapi import (
    File,
    UploadFile,
)
from fastapi import APIRouter, Depends, Response, status, Body
from typing import List, Dict
from sqlalchemy.orm import Session
from datetime import datetime
from modules.whisper.data_classes import *
from modules.utils.paths import BACKEND_CACHE_DIR
from modules.whisper.faster_whisper_inference import FasterWhisperInference
from modules.whisper.base_transcription_pipeline import BaseTranscriptionPipeline
from backend.common.progress import NO_OP_PROGRESS
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

from backend.modal_pool.factory import create_modal_pool, get_max_retries

modal_pool = create_modal_pool()
max_retries_pool = get_max_retries() if modal_pool else 2



def create_progress_callback(identifier: str):
    def progress_callback(progress_value: float):
        update_task_status_in_db(
            identifier=identifier,
            update_data={
                "uuid": identifier,
                "status": TaskStatus.IN_PROGRESS,
                "progress": float(round(progress_value, 2)),
                "updated_at": datetime.utcnow()
            },
        )
    return progress_callback


@functools.lru_cache
def get_pipeline(endpoint_url: Optional[str] = None) -> 'BaseTranscriptionPipeline':
    import os
    from modules.whisper.whisper_factory import WhisperFactory
    config = load_server_config()["whisper"]
    
    # Use WhisperFactory to automatically switch to Modal serverless inference
    # when MODAL_WEB_ENDPOINT_URL is configured.
    inferencer = WhisperFactory.create_whisper_inference(
        whisper_type="faster-whisper",
        output_dir=BACKEND_CACHE_DIR,
        endpoint_url=endpoint_url
    )
    
    # If we are not running on Modal, initialize/update local model settings
    if not os.environ.get("MODAL_WEB_ENDPOINT_URL") and not os.environ.get("MODAL_ENDPOINTS") and not endpoint_url:
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

    is_modal = bool(os.environ.get("MODAL_WEB_ENDPOINT_URL") or os.environ.get("MODAL_ENDPOINTS"))
    progress_thread = None
    if is_modal:
        progress_thread = threading.Thread(target=simulate_progress, daemon=True)
        progress_thread.start()

    progress_callback = create_progress_callback(identifier)
    try:
        try:
            if not is_modal or not modal_pool:
                segments, elapsed_time = get_pipeline().run(
                    audio,
                    NO_OP_PROGRESS,
                    "SRT",
                    False,
                    progress_callback,
                    *params.to_list()
                )
            else:
                last_err = None
                success = False
                for attempt in range(max_retries_pool + 1):
                    try:
                        with modal_pool.acquire() as ep:
                            try:
                                segments, elapsed_time = get_pipeline(endpoint_url=ep).run(
                                    audio,
                                    NO_OP_PROGRESS,
                                    "SRT",
                                    False,
                                    None,
                                    *params.to_list()
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
                            import time
                            time.sleep(0.5)
                if not success:
                    raise last_err or RuntimeError("Modal execution failed on all retries")
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
    except Exception as err:
        update_task_status_in_db(
            identifier=identifier,
            update_data={
                "uuid": identifier,
                "status": TaskStatus.FAILED,
                "error": str(err),
                "updated_at": datetime.utcnow(),
            },
        )
        raise


@transcription_router.post(
    "/",
    response_model=QueueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Transcribe Audio",
    description="Process the provided audio or video file to generate a transcription.",
)
async def transcription(
    file: UploadFile = File(..., description="Audio or video file to transcribe."),
    whisper_params: WhisperParams = Depends(),
    vad_params: VadParams = Depends(),
    bgm_separation_params: BGMSeparationParams = Depends(),
    diarization_params: DiarizationParams = Depends(),
) -> QueueResponse:
    from fastapi import HTTPException
    from backend.queue.enqueue import CeleryEnqueueError, enqueue_task
    from backend.queue.transcription_core import save_audio_to_wav
    from backend.queue.tasks import transcribe_audio_task

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

    save_audio_to_wav(identifier, audio)
    try:
        enqueue_task(transcribe_audio_task, identifier)
    except CeleryEnqueueError as exc:
        update_task_status_in_db(
            identifier,
            {"status": TaskStatus.FAILED, "error": str(exc)},
        )
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return QueueResponse(identifier=identifier, status=TaskStatus.QUEUED, message="Transcription task has queued")


@transcription_router.post("/batch", status_code=201)
async def queue_batch_transcription(
    payload: dict = Body(...),
    session: Session = Depends(get_db_session)
):
    import uuid
    from fastapi import HTTPException
    from backend.db.batch.dao import add_batch_to_db
    from backend.db.batch.models import BatchJob
    from backend.db.task.models import Task, TaskStatus, TaskType
    from backend.queue.enqueue import CeleryEnqueueError, enqueue_task
    from backend.queue.tasks import orchestrate_batch_task

    batch_id = str(uuid.uuid4())
    files_payload = payload.get("files", [])
    selected_ids = [f.get("file_id") for f in files_payload if f.get("file_id")]
    folder_name = payload.get("folder_name", "Batch Job")
    folder_url = payload.get("folder_url", "")

    max_batch_files = int(os.environ.get("BATCH_MAX_FILES", "500"))
    if len(selected_ids) > max_batch_files:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"Batch exceeds max {max_batch_files} files",
        )

    access_mode = payload.get("access_mode", "link")
    connection_id = payload.get("connection_id")
    writeback_enabled = payload.get("writeback", {}).get("enabled", False) if access_mode == "connect" else False

    add_batch_to_db(
        session=session,
        batch_id=batch_id,
        folder_name=folder_name,
        source_url=folder_url,
        total_files=len(selected_ids),
        task_params=payload,
        access_mode=access_mode,
        connection_id=connection_id,
        writeback_enabled=writeback_enabled
    )

    for f in files_payload:
        file_id = f.get("file_id")
        file_name = f.get("name", f"Drive_File_{file_id}")
        source_path = f.get("path")
        parent_id = f.get("parent_id")

        add_task_to_db(
            session=session,
            status=TaskStatus.QUEUED,
            file_name=file_name,
            task_type=TaskType.TRANSCRIPTION,
            task_params=payload,
            batch_id=batch_id,
            source_file_id=file_id,
            source_path=source_path,
            source_parent_id=parent_id
        )

    try:
        enqueue_task(orchestrate_batch_task, batch_id=batch_id, offset=0)
    except CeleryEnqueueError as exc:
        batch = session.query(BatchJob).filter(BatchJob.batch_id == batch_id).first()
        if batch:
            batch.status = "failed"
        for task in session.query(Task).filter(Task.batch_id == batch_id):
            task.status = TaskStatus.FAILED
            task.error = str(exc)
        session.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "batch_id": batch_id,
        "status": "queued",
        "total_files": len(selected_ids),
        "message": "Batch transcription queued"
    }
