from datetime import datetime, timedelta
import pytest
from backend.db.share.models import TranscriptShareToken

def test_share_token_validity():
    now = datetime.utcnow()
    
    # Active valid token
    valid_token = TranscriptShareToken(
        token="tok_12345",
        task_uuid="task-uuid-001",
        expires_at=now + timedelta(hours=24),
        revoked_at=None,
        created_at=now
    )
    assert valid_token.is_valid() is True

    # Expired token
    expired_token = TranscriptShareToken(
        token="tok_67890",
        task_uuid="task-uuid-001",
        expires_at=now - timedelta(hours=1),
        revoked_at=None,
        created_at=now
    )
    assert expired_token.is_valid() is False

    # Revoked token
    revoked_token = TranscriptShareToken(
        token="tok_abcde",
        task_uuid="task-uuid-001",
        expires_at=now + timedelta(hours=24),
        revoked_at=now,
        created_at=now
    )
    assert revoked_token.is_valid() is False
