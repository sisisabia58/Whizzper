from backend.common.health import health_status_code, health_status_label


def test_health_status_code_only_depends_on_database():
    assert health_status_code(True) == 200
    assert health_status_code(False) == 503


def test_health_status_label():
    assert health_status_label(True, True) == "ok"
    assert health_status_label(True, None) == "ok"
    assert health_status_label(True, False) == "degraded"
    assert health_status_label(False, True) == "unhealthy"
