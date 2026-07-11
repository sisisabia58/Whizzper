from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.db.drive.models import DriveConnection
from modules.utils.drive_auth import encrypt_token

def add_connection(
    session: Session,
    owner_key: str,
    email: str,
    sub: str,
    tokens: Dict[str, Any]
) -> DriveConnection:
    conn = DriveConnection(
        owner_key=owner_key,
        account_email=email,
        account_sub=sub,
        access_token_enc=encrypt_token(tokens["access_token"]),
        refresh_token_enc=encrypt_token(tokens["refresh_token"]),
        token_expiry=tokens["token_expiry"],
        scopes=tokens["scopes"]
    )
    session.add(conn)
    session.commit()
    session.refresh(conn)
    return conn

def get_connection_from_db(session: Session, connection_id: str) -> Optional[DriveConnection]:
    return session.query(DriveConnection).filter(DriveConnection.connection_id == connection_id).first()

def list_connections_from_db(session: Session, owner_key: str) -> List[DriveConnection]:
    return session.query(DriveConnection).filter(DriveConnection.owner_key == owner_key).all()

def delete_connection_from_db(session: Session, connection_id: str) -> bool:
    conn = get_connection_from_db(session, connection_id)
    if conn:
        session.delete(conn)
        session.commit()
        return True
    return False
