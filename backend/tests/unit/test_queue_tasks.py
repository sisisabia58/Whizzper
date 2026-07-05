import uuid
from backend.db.db_instance import SessionLocal, engine, Base
from backend.db.models import Task
from backend.queue.celery_app import celery_app
from backend.queue.tasks import run_transcription_task

def test_celery_app_configuration():
    assert celery_app.conf.broker_url is not None

def test_run_transcription_task_callable():
    assert callable(run_transcription_task)

def test_task_execution_eager_lifecycle():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    unique_id = f"test-task-{uuid.uuid4().hex[:8]}"
    
    # Create task record
    t = Task(identifier=unique_id, status="QUEUED", current_stage="queued")
    db.add(t)
    db.commit()
    db.close()
    
    # Run task synchronously in eager mode
    res = run_transcription_task(unique_id, "/tmp/dummy.mp3", {})
    assert res["status"] == "completed"
    
    # Verify DB update
    db2 = SessionLocal()
    updated = db2.query(Task).filter(Task.identifier == unique_id).first()
    assert updated.status == "COMPLETED"
    assert updated.progress_percent == 100
    assert updated.current_stage == "done"
    db2.close()
