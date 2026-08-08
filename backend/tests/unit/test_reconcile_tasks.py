"""Isolated reconcile test — avoids Celery eager cross-test state from orchestrate tests."""
import pytest
from unittest.mock import patch
from datetime import datetime, timedelta

from sqlmodel import SQLModel


@pytest.fixture
def celery_eager():
    from backend.queue.celery_app import celery_app
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = False


@pytest.fixture
def db_engine():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    import backend.db.task.models
    SQLModel.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


def test_reconcile_requeues_stale_in_progress(celery_eager, db_engine):
    engine, SessionLocal = db_engine
    from backend.db.task.models import Task, TaskStatus, TaskType

    session = SessionLocal()
    stale = Task(
        uuid="stale-task",
        status=TaskStatus.IN_PROGRESS,
        task_type=TaskType.TRANSCRIPTION,
        created_at=datetime.utcnow() - timedelta(hours=2),
        updated_at=datetime.utcnow() - timedelta(hours=2),
    )
    session.add(stale)
    session.commit()
    session.close()

    def get_db_session():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    with patch("backend.db.db_instance.get_db_session", get_db_session), patch(
        "backend.db.db_instance.SessionLocal", SessionLocal
    ), patch("backend.db.db_instance.engine", engine):
        from backend.queue import tasks as tasks_mod
        with patch.object(tasks_mod.transcribe_audio_task, "delay") as mock_tx:
            result = tasks_mod.reconcile_stuck_tasks()
            assert result["requeued"] >= 1
            mock_tx.assert_called()
