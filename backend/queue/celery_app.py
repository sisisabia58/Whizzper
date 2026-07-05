import os
from celery import Celery

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery(
    "whizzper_tasks",
    broker=redis_url,
    backend=redis_url
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_always_eager=os.environ.get("USE_TASK_QUEUE", "true").lower() == "false"
)
