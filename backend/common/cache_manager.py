import os
import time
from typing import Optional, Set

from modules.utils.paths import BACKEND_CACHE_DIR


def _active_task_uuids() -> Set[str]:
    """UUIDs for tasks that still need cache files on disk."""
    try:
        from backend.db.db_instance import SessionLocal
        from backend.db.task.models import Task, TaskStatus

        session = SessionLocal()
        try:
            rows = session.query(Task.uuid).filter(
                Task.status.in_([TaskStatus.QUEUED, TaskStatus.IN_PROGRESS])
            ).all()
            return {r[0] for r in rows}
        finally:
            session.close()
    except Exception:
        return set()


def _file_belongs_to_active_task(filepath: str, active_uuids: Set[str]) -> bool:
    basename = os.path.basename(filepath)
    for uuid in active_uuids:
        if basename.startswith(uuid):
            return True
    return False


def cleanup_old_files(cache_dir: str = BACKEND_CACHE_DIR, ttl: Optional[int] = None):
    if ttl is None:
        ttl = int(os.environ.get("CACHE_TTL_SECONDS", "86400"))
    now = time.time()
    place_holder_name = "cached_files_are_generated_here"
    active_uuids = _active_task_uuids()
    for root, dirs, files in os.walk(cache_dir):
        for filename in files:
            if filename == place_holder_name:
                continue
            filepath = os.path.join(root, filename)
            if _file_belongs_to_active_task(filepath, active_uuids):
                continue
            if now - os.path.getmtime(filepath) > ttl:
                try:
                    os.remove(filepath)
                except Exception:
                    print(f"Error removing {filepath}")
                    raise
