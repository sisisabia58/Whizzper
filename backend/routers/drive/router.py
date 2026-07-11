from fastapi import APIRouter, HTTPException, Body, Depends, Response, status
from sqlalchemy.orm import Session
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

@drive_router.post("/scan")
async def scan_drive_folder(payload: dict = Body(...)):
    url = payload.get("folder_url")
    if not url:
        raise HTTPException(status_code=400, detail="Missing folder_url")
        
    folder_id = parse_folder_id(url)
    if not folder_id:
        raise HTTPException(status_code=400, detail="Invalid Google Drive folder link")
        
    try:
        manager = DriveManager()
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
