from datetime import datetime
from backend.queue.celery_app import celery_app
from backend.db.db_instance import SessionLocal
from backend.db.models import Task

@celery_app.task(name="run_transcription_task")
def run_transcription_task(identifier: str, file_path: str, params_dict: dict):
    db = SessionLocal()
    task = db.query(Task).filter(Task.identifier == identifier).first()
    if not task:
        db.close()
        return {"status": "failed", "error": "Task not found"}
    try:
        task.status = "PROCESSING"
        task.current_stage = "transcribing"
        task.started_at = datetime.utcnow()
        db.commit()

        # Pipeline logic integration point
        
        task.status = "COMPLETED"
        task.current_stage = "done"
        task.progress_percent = 100
        task.finished_at = datetime.utcnow()
        db.commit()
        return {"status": "completed", "identifier": identifier}
    except Exception as exc:
        task.status = "FAILED"
        task.current_stage = "failed"
        task.error_message = str(exc)
        db.commit()
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()
