import os
from celery import Celery
from celery.schedules import crontab

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

broker_ssl = None
if redis_url.startswith("rediss://"):
    broker_ssl = {"ssl_cert_reqs": "CERT_NONE"}

celery_app = Celery("whizzper_tasks", broker=redis_url, backend=redis_url)

task_time_limit = int(os.environ.get("CELERY_TASK_TIME_LIMIT", "7200"))
task_soft_limit = int(os.environ.get("CELERY_TASK_SOFT_TIME_LIMIT", "6900"))
visibility_timeout = int(os.environ.get("CELERY_VISIBILITY_TIMEOUT", "10800"))
worker_max_tasks_per_child = int(os.environ.get("CELERY_WORKER_MAX_TASKS_PER_CHILD", "50"))

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_ignore_result=True,
    task_store_errors_even_if_ignored=False,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=3,
    broker_use_ssl=broker_ssl,
    redis_backend_use_ssl=broker_ssl,
    task_always_eager=os.environ.get("USE_TASK_QUEUE", "true").lower() == "false",
    task_routes={
        "download_drive_file_task": {"queue": "download"},
        "transcribe_audio_task": {"queue": "transcribe"},
        "orchestrate_batch_task": {"queue": "orchestrate"},
        "reconcile_stuck_tasks": {"queue": "reconcile"},
    },
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=task_time_limit,
    task_soft_time_limit=task_soft_limit,
    broker_transport_options={"visibility_timeout": visibility_timeout},
    result_backend_transport_options={"visibility_timeout": visibility_timeout},
    visibility_timeout=visibility_timeout,
    worker_max_tasks_per_child=worker_max_tasks_per_child,
    beat_schedule={
        "reconcile-stuck-tasks": {
            "task": "reconcile_stuck_tasks",
            "schedule": crontab(minute="*/5"),
        },
    },
)

import backend.queue.tasks  # noqa: F401 — register task definitions on workers
