from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
from backend.db.db_instance import handle_database_errors
from .models import BatchJob
from backend.db.task.models import Task

@handle_database_errors
def add_batch_to_db(
    session: Session,
    batch_id: str,
    folder_name: str,
    source_url: str,
    total_files: int,
    task_params: dict,
    access_mode: str = "link",
    connection_id: Optional[str] = None,
    writeback_enabled: bool = False
):
    batch = BatchJob(
        batch_id=batch_id,
        folder_name=folder_name,
        source_url=source_url,
        total_files=total_files,
        task_params=task_params,
        status="queued",
        access_mode=access_mode,
        connection_id=connection_id,
        writeback_enabled=writeback_enabled
    )
    session.add(batch)
    session.commit()
    return batch

@handle_database_errors
def get_batch_from_db(batch_id: str, session: Session) -> Optional[BatchJob]:
    return session.query(BatchJob).filter(BatchJob.batch_id == batch_id).first()

@handle_database_errors
def update_batch_rollup(batch_id: str, session: Session):
    batch = get_batch_from_db(batch_id, session)
    if not batch:
        return
    
    children = session.query(Task).filter(Task.batch_id == batch_id).all()
    batch.total_files = len(children)
    batch.completed_files = sum(1 for c in children if c.status == "completed")
    batch.failed_files = sum(1 for c in children if c.status == "failed")
    batch.uploaded_files = sum(1 for c in children if c.writeback_status == "UPLOADED")
    batch.writeback_failed_files = sum(1 for c in children if c.writeback_status == "FAILED")
    
    # Calculate status rollup
    active = sum(1 for c in children if c.status in ["queued", "in_progress"])
    if active > 0:
        batch.status = "in_progress"
    elif batch.completed_files == batch.total_files:
        batch.status = "completed"
        batch.finished_at = datetime.utcnow()
    elif batch.failed_files == batch.total_files:
        batch.status = "failed"
        batch.finished_at = datetime.utcnow()
    else:
        batch.status = "partial_failed"
        batch.finished_at = datetime.utcnow()
        
    batch.updated_at = datetime.utcnow()
    session.commit()
