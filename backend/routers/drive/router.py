from fastapi import APIRouter, HTTPException, Body, Depends, Response, status
from sqlalchemy.orm import Session
from typing import Optional
from backend.db.db_instance import get_db_session
from modules.utils.drive_manager import DriveManager, parse_folder_id
from datetime import datetime

drive_router = APIRouter(prefix="/drive", tags=["Google Drive"])

@drive_router.get("/connections")
async def get_connections(owner_key: str, session: Session = Depends(get_db_session)):
    from backend.db.drive.dao import list_connections_from_db
    conns = list_connections_from_db(session, owner_key)
    return {
        "connections": [
            {
                "connection_id": c.connection_id,
                "account_email": c.account_email,
                "status": c.status
            } for c in conns
        ]
    }

@drive_router.delete("/connections/{connection_id}")
async def delete_connection(connection_id: str, session: Session = Depends(get_db_session)):
    from backend.db.drive.dao import delete_connection_from_db
    if delete_connection_from_db(session, connection_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise HTTPException(status_code=404, detail="Connection not found")

@drive_router.get("/folders")
async def get_folders(
    connection_id: str,
    parent_id: Optional[str] = None,
    page_token: Optional[str] = None,
    session: Session = Depends(get_db_session)
):
    from backend.db.drive.dao import get_connection_from_db
    from modules.utils.drive_auth import decrypt_token
    import os
    conn = get_connection_from_db(session, connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
        
    creds_dict = {
        "token": decrypt_token(conn.access_token_enc),
        "refresh_token": decrypt_token(conn.refresh_token_enc),
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": os.environ.get("GOOGLE_OAUTH_CLIENT_ID"),
        "client_secret": os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    }
    
    manager = DriveManager(credentials_dict=creds_dict)
    results = manager.list_folders(parent_id, page_token)
    return results

@drive_router.post("/scan")
async def scan_drive_folder(payload: dict = Body(...), session: Session = Depends(get_db_session)):
    connection_id = payload.get("connection_id")
    folder_id = payload.get("folder_id")
    
    if connection_id and folder_id:
        from backend.db.drive.dao import get_connection_from_db
        from modules.utils.drive_auth import decrypt_token
        import os
        
        conn = get_connection_from_db(session, connection_id)
        if not conn:
            raise HTTPException(status_code=404, detail="Connection not found")
            
        creds_dict = {
            "token": decrypt_token(conn.access_token_enc),
            "refresh_token": decrypt_token(conn.refresh_token_enc),
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": os.environ.get("GOOGLE_OAUTH_CLIENT_ID"),
            "client_secret": os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
        }
        manager = DriveManager(credentials_dict=creds_dict)
    else:
        url = payload.get("folder_url")
        if not url:
            raise HTTPException(status_code=400, detail="Missing folder_url or connection_id/folder_id")
            
        folder_id = parse_folder_id(url)
        if not folder_id:
            raise HTTPException(status_code=400, detail="Invalid Google Drive folder link")
            
        manager = DriveManager()
        
    try:
        files = manager.scan_folder(folder_id)
        
        media_files = [f for f in files if f["is_media"]]
        total_duration = sum(f["duration_sec"] for f in media_files if f["duration_sec"])
        
        return {
            "folder_name": "Google Drive Folder",
            "scanned_at": datetime.utcnow().isoformat(),
            "summary": {
                "processable": len(media_files),
                "skipped": len(files) - len(media_files),
                "total_duration_sec": total_duration
            },
            "files": files
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Google Drive scan failed: {str(e)}")
