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


def test_add_task_to_db_cleans_infinity():
    from backend.db.task.dao import add_task_to_db
    from backend.db.task.models import Task as DBTask
    from sqlmodel import SQLModel
    from sqlalchemy import text
    import backend.db.task.models
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS tasks"))
    Base.metadata.create_all(bind=engine)
    SQLModel.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    test_params = {
        "vad": {
            "max_speech_duration_s": float('inf'),
            "threshold": float('nan'),
            "normal_float": 1.5
        }
    }
    
    uuid_str = add_task_to_db(
        session=db,
        status="queued",
        task_type="transcription",
        task_params=test_params
    )
    db.close()
    
    # Retrieve it
    db2 = SessionLocal()
    task = db2.query(DBTask).filter_by(uuid=uuid_str).first()
    assert task is not None
    assert task.task_params["vad"]["max_speech_duration_s"] is None
    assert task.task_params["vad"]["threshold"] is None
    assert task.task_params["vad"]["normal_float"] == 1.5
    db2.close()

