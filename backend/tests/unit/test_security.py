import backend.tests.unit.ml_stubs  # noqa: F401

import pytest
from fastapi import HTTPException

from backend.common.security import cors_origins, require_api_key


def test_cors_origins_parses_env(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com,http://localhost:3000")
    assert cors_origins() == ["https://app.example.com", "http://localhost:3000"]


def test_require_api_key_skipped_when_unset(monkeypatch):
    monkeypatch.delenv("WHIZZPER_API_KEY", raising=False)
    require_api_key(x_api_key=None)


def test_require_api_key_rejects_missing(monkeypatch):
    monkeypatch.setenv("WHIZZPER_API_KEY", "secret-key")
    with pytest.raises(HTTPException) as exc:
        require_api_key(x_api_key=None)
    assert exc.value.status_code == 401


def test_require_api_key_accepts_valid(monkeypatch):
    monkeypatch.setenv("WHIZZPER_API_KEY", "secret-key")
    require_api_key(x_api_key="secret-key")
