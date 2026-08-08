def test_celery_task_routes():
    from backend.queue.celery_app import celery_app
    routes = celery_app.conf.task_routes
    assert routes["transcribe_audio_task"]["queue"] == "transcribe"


def test_celery_acks_late_enabled():
    from backend.queue.celery_app import celery_app
    assert celery_app.conf.task_acks_late is True


def test_visibility_timeout_exceeds_time_limit():
    from backend.queue.celery_app import celery_app
    visibility = celery_app.conf.broker_transport_options["visibility_timeout"]
    time_limit = celery_app.conf.task_time_limit
    assert visibility > time_limit
