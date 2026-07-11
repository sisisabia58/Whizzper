import os
import pytest
from backend.modal_pool.config import get_pool_config

def test_parses_comma_separated_endpoints(monkeypatch):
    monkeypatch.setenv("MODAL_ENDPOINTS", "https://ep1.modal.run,https://ep2.modal.run")
    config = get_pool_config()
    assert config["endpoints"] == ["https://ep1.modal.run", "https://ep2.modal.run"]

def test_falls_back_to_single_web_endpoint_url(monkeypatch):
    monkeypatch.delenv("MODAL_ENDPOINTS", raising=False)
    monkeypatch.setenv("MODAL_WEB_ENDPOINT_URL", "https://fallback.modal.run")
    config = get_pool_config()
    assert config["endpoints"] == ["https://fallback.modal.run"]

def test_empty_config_raises_clear_error(monkeypatch):
    monkeypatch.delenv("MODAL_ENDPOINTS", raising=False)
    monkeypatch.delenv("MODAL_WEB_ENDPOINT_URL", raising=False)
    with pytest.raises(ValueError, match="No Modal endpoints configured"):
        get_pool_config()
