import os
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
    import backend.db.batch.models
    SQLModel.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


def _db_patches(engine, SessionLocal):
    def get_db_session():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    return (
        patch("backend.db.db_instance.get_db_session", get_db_session),
        patch("backend.db.db_instance.SessionLocal", SessionLocal),
        patch("backend.db.db_instance.engine", engine),
    )


def test_orchestrate_batch_enqueues_chunk_only(celery_eager, db_engine):
    engine, SessionLocal = db_engine
    from backend.db.task.models import Task, TaskStatus, TaskType
    from backend.db.batch.dao import add_batch_to_db

    session = SessionLocal()
    batch_id = "batch-chunk-test"
    add_batch_to_db(
        session=session,
        batch_id=batch_id,
        folder_name="Chunk Test",
        source_url="",
        total_files=50,
        task_params={},
    )
    for i in range(50):
        session.add(
            Task(
                uuid=f"task-{i}",
                batch_id=batch_id,
                source_file_id=f"file-{i}",
                file_name=f"file-{i}.mp3",
                status=TaskStatus.QUEUED,
                task_type=TaskType.TRANSCRIPTION,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
    session.commit()
    session.close()

    patches = _db_patches(engine, SessionLocal)
    with patches[0], patches[1], patches[2]:
        from backend.queue import tasks as tasks_mod
        with patch.object(tasks_mod.download_drive_file_task, "delay") as mock_dl:
            tasks_mod.orchestrate_batch_task(batch_id, offset=0)
            chunk = int(os.environ.get("BATCH_FANOUT_CHUNK_SIZE", "25"))
            assert mock_dl.call_count == chunk


def test_transcribe_skips_cancelled_task(celery_eager, db_engine):
    engine, SessionLocal = db_engine
    from backend.db.task.models import Task, TaskStatus, TaskType

    session = SessionLocal()
    task = Task(
        uuid="cancelled-uuid",
        status=TaskStatus.CANCELLED,
        task_type=TaskType.TRANSCRIPTION,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(task)
    session.commit()
    session.close()

    patches = _db_patches(engine, SessionLocal)
    with patches[0], patches[1], patches[2]:
        from backend.queue.tasks import transcribe_audio_task
        result = transcribe_audio_task("cancelled-uuid")
    assert result["skipped"] is True
