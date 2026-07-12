import os
import base64
from typing import Optional
from cryptography.fernet import Fernet

def get_fernet() -> Fernet:
    key = os.environ.get("DRIVE_TOKEN_ENC_KEY")
    if not key:
        raise ValueError("DRIVE_TOKEN_ENC_KEY environment variable is not configured.")
    return Fernet(key.encode())

def encrypt_token(token: str) -> bytes:
    if not token:
        return b""
    f = get_fernet()
    return f.encrypt(token.encode())

def decrypt_token(enc_token: bytes) -> str:
    if not enc_token:
        return ""
    f = get_fernet()
    return f.decrypt(enc_token).decode()

def build_consent_url(state: str) -> str:
    from google_auth_oauthlib.flow import Flow
    client_config = {
        "web": {
            "client_id": os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "mock-id"),
            "client_secret": os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "mock-secret"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    scopes = os.environ.get("DRIVE_OAUTH_SCOPES", "https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/userinfo.email").split()
    redirect_uri = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8080/api/auth/google/callback")
    
    flow = Flow.from_client_config(client_config, scopes=scopes)
    flow.redirect_uri = redirect_uri
    
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=state
    )
    return auth_url

def exchange_code(code: str) -> dict:
    from google_auth_oauthlib.flow import Flow
    client_config = {
        "web": {
            "client_id": os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "mock-id"),
            "client_secret": os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "mock-secret"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    scopes = os.environ.get("DRIVE_OAUTH_SCOPES", "https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/userinfo.email").split()
    redirect_uri = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8080/api/auth/google/callback")
    
    flow = Flow.from_client_config(client_config, scopes=scopes)
    flow.redirect_uri = redirect_uri
    flow.fetch_token(code=code)
    
    credentials = flow.credentials
    return {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_expiry": credentials.expiry,
        "scopes": " ".join(credentials.scopes)
    }
