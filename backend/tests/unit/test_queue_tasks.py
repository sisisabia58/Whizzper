import pytest
from backend.db.db_instance import engine, Base
from backend.queue.celery_app import celery_app


def test_celery_app_configuration():
    assert celery_app.conf.broker_url is not None


def test_add_task_to_db_cleans_infinity():
    from backend.db.task.dao import add_task_to_db
    from backend.db.task.models import Task as DBTask
    from sqlmodel import SQLModel
    from sqlalchemy import text
    from backend.db.db_instance import SessionLocal
    import backend.db.task.models

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS tasks"))
    Base.metadata.create_all(bind=engine)
    SQLModel.metadata.create_all(bind=engine)
    db = SessionLocal()

    test_params = {
        "vad": {
            "max_speech_duration_s": float("inf"),
            "threshold": float("nan"),
            "normal_float": 1.5,
        }
    }

    uuid_str = add_task_to_db(
        session=db,
        status="queued",
        task_type="transcription",
        task_params=test_params,
    )
    db.close()

    db2 = SessionLocal()
    task = db2.query(DBTask).filter_by(uuid=uuid_str).first()
    assert task is not None
    assert task.task_params["vad"]["max_speech_duration_s"] is None
    assert task.task_params["vad"]["threshold"] is None
    assert task.task_params["vad"]["normal_float"] == 1.5
    db2.close()
