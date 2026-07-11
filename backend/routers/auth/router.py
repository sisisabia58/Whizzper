import uuid
import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from backend.db.db_instance import get_db_session
from backend.db.drive.dao import add_connection
from modules.utils.drive_auth import build_consent_url, exchange_code

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

@auth_router.get("/google/start")
async def start_google_auth(owner_key: str):
    state = str(uuid.uuid4())
    url = build_consent_url(state)
    return {"authorize_url": url, "state": state}

@auth_router.get("/google/callback")
async def google_callback(code: str, state: str, session: Session = Depends(get_db_session)):
    try:
        tokens = exchange_code(code)
        # Fetch basic email/sub from profile API
        import requests
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        profile = requests.get("https://www.googleapis.com/oauth2/v3/userinfo", headers=headers).json()
        
        email = profile.get("email", "unknown@email.com")
        sub = profile.get("sub", "unknown-sub")
        
        conn = add_connection(session, "interim-owner", email, sub, tokens)
        return RedirectResponse(url=f"/#connection={conn.connection_id}&email={email}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {str(e)}")
