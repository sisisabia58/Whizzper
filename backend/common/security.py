import os

from fastapi import Header, HTTPException, status


def get_api_key() -> str | None:
    key = os.environ.get("WHIZZPER_API_KEY", "").strip()
    return key or None


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """When WHIZZPER_API_KEY is set, mutating endpoints must present X-API-Key."""
    expected = get_api_key()
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


def cors_origins() -> list[str]:
    raw = os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173",
    )
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins if origins else ["http://localhost:8000"]
