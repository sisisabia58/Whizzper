from backend.db.db_instance import SessionLocal, engine, Base
from backend.db.models import Task
from backend.queue.tasks import run_transcription_task

def test_task_execution_eager_lifecycle():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Create task record
    t = Task(identifier="test-task-999", status="QUEUED", current_stage="queued")
    db.add(t)
    db.commit()
    db.close()
    
    # Run task synchronously in eager mode
    res = run_transcription_task("test-task-999", "/tmp/dummy.mp3", {})
    assert res["status"] == "completed"
    
    # Verify DB update
    db2 = SessionLocal()
    updated = db2.query(Task).filter(Task.identifier == "test-task-999").first()
    assert updated.status == "COMPLETED"
    assert updated.progress_percent == 100
    assert updated.current_stage == "done"
    db2.close()
