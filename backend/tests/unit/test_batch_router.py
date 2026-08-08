import os
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ.setdefault("MODAL_WEB_ENDPOINT_URL", "https://mock-endpoint.modal.run")


@patch("backend.queue.tasks.orchestrate_batch_task")
def test_queue_batch_transcription(mock_orchestrate):
    from backend.main import app
    from backend.db.db_instance import engine, SessionLocal
    from sqlmodel import SQLModel
    import backend.db.task.models
    import backend.db.batch.models

    SQLModel.metadata.create_all(bind=engine)

    payload = {
        "folder_url": "https://drive.google.com/drive/folders/test-batch-folder",
        "folder_name": "Test Folder Name",
        "files": [
            {"file_id": "file1", "name": "first_file.mp3", "path": "day1/first_file.mp3"},
            {"file_id": "file2", "name": "second_file.wav", "path": "day2/second_file.wav"},
        ],
        "whisper_params": {"model_size": "small", "compute_type": "int8", "lang": "en"},
        "vad_params": {"vad_filter": False},
        "bgm_separation_params": {"is_separate_bgm": False},
        "diarization_params": {"is_diarize": False},
    }

    with TestClient(app) as test_client:
        response = test_client.post("/api/transcription/batch", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "batch_id" in data
    assert data["status"] == "queued"
    assert data["total_files"] == 2

    from backend.db.batch.models import BatchJob
    from backend.db.task.models import Task

    session = SessionLocal()
    batch = session.query(BatchJob).filter(BatchJob.batch_id == data["batch_id"]).first()
    assert batch is not None
    assert batch.folder_name == "Test Folder Name"
    assert batch.total_files == 2

    tasks = session.query(Task).filter(Task.batch_id == data["batch_id"]).all()
    assert len(tasks) == 2
    assert {t.source_file_id for t in tasks} == {"file1", "file2"}
    assert {t.file_name for t in tasks} == {"first_file.mp3", "second_file.wav"}
    assert {t.source_path for t in tasks} == {"day1/first_file.mp3", "day2/second_file.wav"}
    session.close()
