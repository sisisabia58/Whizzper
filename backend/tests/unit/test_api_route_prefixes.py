import backend.tests.unit.ml_stubs  # noqa: F401

import backend.main as main_module


def test_transcription_upload_route_uses_api_prefix():
    openapi_paths = main_module.app.openapi()["paths"]
    assert any(path.startswith("/api/transcription") for path in openapi_paths)
