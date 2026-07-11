import pytest
from datetime import datetime
from backend.db.drive.dao import add_connection, get_connection_from_db
from backend.db.drive.models import DriveConnection

def test_add_and_retrieve_connection(monkeypatch):
    monkeypatch.setenv("DRIVE_TOKEN_ENC_KEY", "u-6bM0kZl847-qA6u9Q2h6_wHmxrX2r8Y6qB3k5i6u0=")
    from backend.db.db_instance import SessionLocal, engine
    from sqlmodel import SQLModel
    import backend.db.drive.models
    
    SQLModel.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        tokens = {
            "access_token": "atok",
            "refresh_token": "rtok",
            "token_expiry": datetime.utcnow(),
            "scopes": "https://drive.file"
        }
        conn = add_connection(session, "user1", "user@email.com", "sub123", tokens)
        assert conn.connection_id is not None
        
        retrieved = get_connection_from_db(session, conn.connection_id)
        assert retrieved.account_email == "user@email.com"
    finally:
        session.close()
