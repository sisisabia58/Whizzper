import os
import time
import wave
import pytest
from datetime import datetime
from unittest.mock import patch

from sqlmodel import SQLModel


def test_cleanup_skips_wav_for_queued_tasks(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.db.task.models import Task, TaskStatus, TaskType

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setenv("CACHE_TTL_SECONDS", "1")

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    task_uuid = "active-task-uuid-12345"
    wav_path = cache_dir / f"{task_uuid}.wav"
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 1600)

    session = SessionLocal()
    session.add(
        Task(
            uuid=task_uuid,
            status=TaskStatus.QUEUED,
            task_type=TaskType.TRANSCRIPTION,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    )
    session.commit()
    session.close()

    time.sleep(1.1)
    with patch("backend.common.cache_manager.BACKEND_CACHE_DIR", str(cache_dir)), patch(
        "backend.db.db_instance.SessionLocal", SessionLocal
    ):
        from backend.common.cache_manager import cleanup_old_files
        cleanup_old_files(cache_dir=str(cache_dir), ttl=1)

    assert wav_path.exists()
