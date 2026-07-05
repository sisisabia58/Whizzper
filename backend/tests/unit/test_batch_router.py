import sys
import os
import types
from importlib.machinery import ModuleSpec
from unittest.mock import MagicMock, patch

# Prevent local model/pipeline weight loading during unit tests
os.environ["MODAL_WEB_ENDPOINT_URL"] = "https://mock-endpoint.modal.run"

# Stub pyannote and torchaudio as real ModuleType instances with ModuleSpec
for name in ['torchaudio', 'pyannote', 'pyannote.audio', 'pyannote.audio.core', 'pyannote.audio.core.io']:
    mod = types.ModuleType(name)
    mod.__spec__ = ModuleSpec(name, None)
    sys.modules[name] = mod

sys.modules['torchaudio'].AudioMetaData = object
sys.modules['pyannote.audio'].Pipeline = MagicMock()

from fastapi.testclient import TestClient
from backend.main import app
from backend.db.db_instance import engine, SessionLocal
from sqlmodel import SQLModel
from sqlalchemy import text

client = TestClient(app)

@patch("backend.routers.transcription.router.run_batch_dispatcher")
def test_queue_batch_transcription(mock_dispatcher):
    from backend.db.db_instance import engine
    from sqlmodel import SQLModel
    import backend.db.task.models
    import backend.db.batch.models
    SQLModel.metadata.create_all(bind=engine)

    payload = {
        "folder_url": "https://drive.google.com/drive/folders/test-batch-folder",
        "folder_name": "Test Folder Name",
        "selected_file_ids": ["file1", "file2"],
        "whisper_params": {"model_size": "small", "compute_type": "int8", "lang": "en"},
        "vad_params": {"vad_filter": False},
        "bgm_separation_params": {"is_separate_bgm": False},
        "diarization_params": {"is_diarize": False}
    }

    with TestClient(app) as test_client:
        response = test_client.post("/api/transcription/batch", json=payload)
    assert response.status_code == 201
    
    data = response.json()
    assert "batch_id" in data
    assert data["status"] == "queued"
    assert data["total_files"] == 2

    # Verify database state
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
    session.close()
