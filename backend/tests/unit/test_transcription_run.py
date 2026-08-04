import backend.tests.unit.ml_stubs  # noqa: F401

import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

import backend.routers.transcription.router as transcription_router_module


@pytest.fixture
def task_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlmodel import SQLModel
    import backend.db.task.models  # noqa: F401

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    from backend.db.task.models import Task, TaskStatus, TaskType

    task = Task(
        uuid="task-fail-001",
        status=TaskStatus.QUEUED,
        task_type=TaskType.TRANSCRIPTION,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(task)
    session.commit()
    session.close()
    return engine, SessionLocal


def test_run_transcription_marks_task_failed_when_pipeline_raises(task_db):
    """When inference fails, the task must not remain in_progress forever."""
    engine, SessionLocal = task_db

    with patch("backend.db.db_instance.engine", engine), patch(
        "backend.db.db_instance.SessionLocal", SessionLocal
    ), patch.object(
        transcription_router_module, "get_pipeline"
    ) as mock_get_pipeline:
        mock_pipeline = MagicMock()
        mock_pipeline.run.side_effect = RuntimeError("inference exploded")
        mock_get_pipeline.return_value = mock_pipeline

        from backend.db.task.models import Task, TaskStatus
        from modules.whisper.data_classes import TranscriptionPipelineParams

        with pytest.raises(RuntimeError, match="inference exploded"):
            transcription_router_module.run_transcription(
                audio=np.zeros(16000, dtype=np.float32),
                params=TranscriptionPipelineParams(),
                identifier="task-fail-001",
            )

        session = SessionLocal()
        task = session.query(Task).filter(Task.uuid == "task-fail-001").one()
        assert task.status == TaskStatus.FAILED
        assert "inference exploded" in (task.error or "")
        session.close()


def test_progress_callback_stores_native_float_for_numpy_progress():
    """Postgres cannot adapt numpy scalars; progress must be a Python float."""
    captured = {}

    def capture_update(identifier, update_data, session=None):
        captured["progress"] = update_data["progress"]

    with patch.object(
        transcription_router_module,
        "update_task_status_in_db",
        side_effect=capture_update,
    ):
        callback = transcription_router_module.create_progress_callback(
            "task-progress-001"
        )
        callback(np.float64(0.42))

    progress = captured["progress"]
    assert type(progress) is float
    assert progress == pytest.approx(0.42)
