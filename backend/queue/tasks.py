import os
from datetime import datetime, timedelta

from backend.queue.celery_app import celery_app
from backend.db import db_instance
from backend.db.task.models import Task, TaskStatus
from backend.db.batch.dao import update_batch_rollup
from backend.queue.batch_state import fanout_chunk_size, reschedule_seconds
from backend.queue.audio_paths import wav_path_for_task, wav_exists


def _get_task_session():
    return next(db_instance.get_db_session())


@celery_app.task(name="orchestrate_batch_task", bind=True, max_retries=0)
def orchestrate_batch_task(self, batch_id: str, offset: int = 0):
    session = _get_task_session()
    try:
        pending = (
            session.query(Task)
            .filter(
                Task.batch_id == batch_id,
                Task.status == TaskStatus.QUEUED,
                Task.source_file_id.isnot(None),
            )
            .order_by(Task.id)
            .all()
        )
        chunk_size = fanout_chunk_size()
        chunk = pending[offset:offset + chunk_size]
        for task in chunk:
            task.status = TaskStatus.IN_PROGRESS
            task.progress = 0.01
            task.updated_at = datetime.utcnow()
            session.commit()
            download_drive_file_task.delay(batch_id, task.source_file_id)

        next_offset = offset + len(chunk)
        if next_offset < len(pending):
            orchestrate_batch_task.apply_async(
                args=[batch_id, next_offset],
                countdown=reschedule_seconds(),
            )
        return {"batch_id": batch_id, "enqueued": len(chunk), "offset": offset}
    finally:
        session.close()


@celery_app.task(name="download_drive_file_task", bind=True, max_retries=3, default_retry_delay=30)
def download_drive_file_task(self, batch_id: str, file_id: str):
    from backend.queue.transcription_core import get_drive_manager, load_audio_from_wav

    session = _get_task_session()
    try:
        task = (
            session.query(Task)
            .filter(Task.batch_id == batch_id, Task.source_file_id == file_id)
            .first()
        )
        if not task:
            return {"skipped": True, "reason": "not_found"}
        if task.status in (TaskStatus.CANCELLED, TaskStatus.COMPLETED):
            return {"skipped": True, "reason": str(task.status)}

        task_params = task.task_params or {}
        wav_path = wav_path_for_task(task.uuid)

        if wav_exists(task.uuid):
            transcribe_audio_task.delay(task.uuid)
            return {"status": "already_downloaded", "uuid": task.uuid}

        task.status = TaskStatus.IN_PROGRESS
        task.progress = 0.05
        task.updated_at = datetime.utcnow()
        session.commit()

        manager = get_drive_manager(task_params, session)
        manager.download_and_extract_audio(file_id, wav_path)
        _, duration = load_audio_from_wav(wav_path)
        task.audio_duration = duration
        session.commit()

        transcribe_audio_task.delay(task.uuid)
        return {"status": "downloaded", "uuid": task.uuid}
    except Exception as exc:
        task = session.query(Task).filter(
            Task.batch_id == batch_id, Task.source_file_id == file_id
        ).first()
        if task:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            task.updated_at = datetime.utcnow()
            session.commit()
            update_batch_rollup(batch_id, session)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise
    finally:
        session.close()


@celery_app.task(name="transcribe_audio_task", bind=True, max_retries=2, default_retry_delay=60)
def transcribe_audio_task(self, task_uuid: str):
    session = _get_task_session()
    try:
        task = session.query(Task).filter(Task.uuid == task_uuid).first()
        if not task:
            return {"skipped": True, "reason": "not_found"}
        if task.status == TaskStatus.CANCELLED:
            return {"skipped": True, "reason": "cancelled"}
        if task.status == TaskStatus.COMPLETED:
            return {"skipped": True, "reason": "already_completed"}
        batch_id = task.batch_id
        source_file_id = task.source_file_id
        task_params = task.task_params or {}
    finally:
        session.close()

    from backend.common.observability import TASKS_TOTAL, TASK_DURATION
    from backend.queue.transcription_core import (
        load_audio_from_wav,
        params_from_task_dict,
        run_transcription_inference,
        run_writeback,
    )

    session = _get_task_session()
    wav_path = wav_path_for_task(task_uuid)
    try:
        task = session.query(Task).filter(Task.uuid == task_uuid).first()
        if not task:
            return {"skipped": True, "reason": "not_found"}

        params = params_from_task_dict(task_params)

        if not wav_exists(task_uuid):
            if source_file_id and batch_id:
                download_drive_file_task.delay(batch_id, source_file_id)
                return {"status": "awaiting_download", "uuid": task_uuid}
            raise FileNotFoundError(f"Audio not found for task {task_uuid}")

        task.status = TaskStatus.IN_PROGRESS
        task.progress = 0.15
        task.updated_at = datetime.utcnow()
        session.commit()

        audio, duration = load_audio_from_wav(wav_path)
        if not task.audio_duration:
            task.audio_duration = duration
            session.commit()

        with TASK_DURATION.time():
            segments, elapsed_time = run_transcription_inference(task_uuid, audio, params)
        segment_dicts = [seg.model_dump() for seg in segments]

        task.status = TaskStatus.COMPLETED
        task.result = segment_dicts
        task.duration = elapsed_time
        task.progress = 1.0
        task.updated_at = datetime.utcnow()

        if task.batch_id and task_params.get("access_mode") == "connect":
            run_writeback(session, task, task_params, segment_dicts)

        session.commit()
        if task.batch_id:
            update_batch_rollup(task.batch_id, session)

        TASKS_TOTAL.labels(status="completed").inc()
        return {"status": "completed", "uuid": task_uuid}
    except Exception as exc:
        TASKS_TOTAL.labels(status="failed").inc()
        task = session.query(Task).filter(Task.uuid == task_uuid).first()
        if task:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            task.updated_at = datetime.utcnow()
            session.commit()
            if task.batch_id:
                update_batch_rollup(task.batch_id, session)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise
    finally:
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except OSError:
                pass
        session.close()


@celery_app.task(name="reconcile_stuck_tasks")
def reconcile_stuck_tasks():
    stuck_minutes = int(os.environ.get("STUCK_TASK_MINUTES", "30"))
    cutoff = datetime.utcnow() - timedelta(minutes=stuck_minutes)
    session = _get_task_session()
    requeued = 0
    try:
        stuck = (
            session.query(Task)
            .filter(Task.status == TaskStatus.IN_PROGRESS, Task.updated_at < cutoff)
            .all()
        )
        for task in stuck:
            task.status = TaskStatus.QUEUED
            task.progress = 0.0
            task.error = "Requeued after worker timeout"
            session.commit()
            if task.source_file_id and task.batch_id and not wav_exists(task.uuid):
                download_drive_file_task.delay(task.batch_id, task.source_file_id)
            else:
                transcribe_audio_task.delay(task.uuid)
            requeued += 1
        return {"requeued": requeued}
    finally:
        session.close()
