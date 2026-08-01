import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from sqlmodel import SQLModel, create_engine, Session
from sqlmodel.pool import StaticPool

from backend.db.db_instance import get_db_session
from backend.db.task.models import Task, TaskStatus
from backend.db.share.models import TranscriptShareToken
from backend.routers.share.router import share_router

# Create lightweight test engine and app instance
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

SQLModel.metadata.create_all(test_engine)

def get_test_db():
    with Session(test_engine) as session:
        yield session

test_app = FastAPI()
test_app.dependency_overrides[get_db_session] = get_test_db
test_app.include_router(share_router)

client = TestClient(test_app)

def test_share_token_creation_and_html_render():
    # 1. Create a dummy completed task
    with Session(test_engine) as db:
        dummy_task = Task(
            uuid="test-task-share-123",
            status=TaskStatus.COMPLETED,
            file_name="test.mp3",
            result={
                "segments": [
                    {"id": 0, "start": 0.0, "end": 2.5, "text": " Hello world"},
                    {"id": 1, "start": 2.5, "end": 5.0, "text": " Testing google translate proxy"}
                ]
            }
        )
        db.add(dummy_task)
        db.commit()

    # 2. Generate share token via POST endpoint
    response = client.post("/api/transcripts/test-task-share-123/share")
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    token = data["token"]
    assert data["share_url"].endswith(f"/transcripts/share/{token}")

    # 3. Access public HTML route
    html_resp = client.get(f"/transcripts/share/{token}")
    assert html_resp.status_code == 200
    html_content = html_resp.text

    # Verify noindex meta tag
    assert '<meta name="robots" content="noindex, nofollow"' in html_content
    # Verify container and data-total
    assert 'id="transcript-container"' in html_content
    assert 'data-total="2"' in html_content
    # Verify timing data attributes and inner spoken text
    assert 'data-index="0"' in html_content
    assert 'data-start="0.0"' in html_content
    assert 'data-end="2.5"' in html_content
    assert 'Hello world' in html_content

    # TurboScribe-style flat blocks with notranslate timestamps
    assert 'class="segment-index notranslate"' in html_content
    assert 'class="segment-time notranslate"' in html_content
    assert '00:00:00,000 --> 00:00:02,500' in html_content

    # TurboScribe-style: translate=yes on text, hidden download mirror, no scroll sweep
    assert 'translate="yes"' in html_content
    assert 'id="download-source"' in html_content
    assert 'class="download-source' in html_content
    assert 'font-size: 0.01px' in html_content
    assert 'scrollIntoView' not in html_content
    assert 'sweepTranslation' not in html_content
    assert 'getElementById(\'download-source\')' in html_content

    # 4. Revoke token
    del_resp = client.delete(f"/api/transcripts/test-task-share-123/share/{token}")
    assert del_resp.status_code == 200

    # 5. Access revoked HTML route returns 404/410 page
    html_revoked = client.get(f"/transcripts/share/{token}")
    assert html_revoked.status_code in [404, 410]
    assert "This link is no longer available" in html_revoked.text
