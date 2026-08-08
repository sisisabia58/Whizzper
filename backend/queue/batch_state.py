import os
from typing import Optional

from backend.db.batch.dao import get_batch_from_db, update_batch_rollup
from backend.db.task.models import Task, TaskStatus


def fanout_chunk_size() -> int:
    return int(os.environ.get("BATCH_FANOUT_CHUNK_SIZE", "25"))


def reschedule_seconds() -> int:
    return int(os.environ.get("ORCHESTRATOR_RESCHEDULE_SECONDS", "10"))


def cancel_batch(batch_id: str, session) -> int:
    batch = get_batch_from_db(batch_id, session)
    if not batch:
        return 0
    children = session.query(Task).filter(Task.batch_id == batch_id).all()
    count = 0
    for child in children:
        if child.status in (TaskStatus.QUEUED, TaskStatus.IN_PROGRESS):
            child.status = TaskStatus.CANCELLED
            count += 1
    batch.status = "cancelled"
    session.commit()
    return count


def mark_batch_rollup(batch_id: str, session) -> None:
    if batch_id:
        update_batch_rollup(batch_id, session)
