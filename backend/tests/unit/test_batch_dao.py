import pytest
from uuid import uuid4
from backend.db.db_instance import SessionLocal, Base
from backend.db.batch.dao import add_batch_to_db, get_batch_from_db, update_batch_rollup
from backend.db.task.dao import add_task_to_db
from backend.db.task.models import TaskStatus
from backend.db.db_instance import engine
from sqlmodel import SQLModel
import backend.db.batch.models
import backend.db.task.models

def test_batch_rollup_calculation():
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS tasks"))
        conn.execute(text("DROP TABLE IF EXISTS batch_jobs"))
    SQLModel.metadata.create_all(bind=engine)
    session = SessionLocal()
    batch_id = str(uuid4())
    add_batch_to_db(
        session=session,
        batch_id=batch_id,
        folder_name="Test Folder",
        source_url="https://drive.google.com/test",
        total_files=2,
        task_params={}
    )
    
    # Create two tasks, one completed, one failed
    add_task_to_db(session=session, status=TaskStatus.COMPLETED, batch_id=batch_id, file_name="file1.mp3")
    add_task_to_db(session=session, status=TaskStatus.FAILED, batch_id=batch_id, file_name="file2.mp3")
    
    update_batch_rollup(batch_id=batch_id, session=session)
    batch = get_batch_from_db(batch_id, session)
    
    assert batch.completed_files == 1
    assert batch.failed_files == 1
    assert batch.status == "partial_failed"
    session.close()
