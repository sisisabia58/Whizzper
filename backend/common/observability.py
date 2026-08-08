import logging
import os
import sentry_sdk
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

# Metrics
TASKS_TOTAL = Counter("whizzper_tasks_total", "Total tasks processed", ["status"])
TASK_DURATION = Histogram("whizzper_task_duration_seconds", "Task duration in seconds")
QUEUE_DEPTH = Gauge("whizzper_queue_depth", "Celery broker queue depth (download + transcribe)")
BATCHES_IN_PROGRESS = Gauge(
    "whizzper_batches_in_progress",
    "Batch jobs with status=in_progress",
)

CELERY_QUEUE_NAMES = ("download", "transcribe", "orchestrate", "reconcile")


def _redis_queue_depth() -> int:
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        return 0
    try:
        import redis

        client = redis.from_url(redis_url, socket_connect_timeout=1)
        depth = 0
        for queue_name in CELERY_QUEUE_NAMES:
            depth += int(client.llen(queue_name))
        return depth
    except Exception as exc:
        logger.debug("queue depth probe failed: %s", exc)
        return 0


def _batches_in_progress_count() -> int:
    try:
        from backend.db.db_instance import SessionLocal
        from backend.db.batch.models import BatchJob

        session = SessionLocal()
        try:
            return session.query(BatchJob).filter(BatchJob.status == "in_progress").count()
        finally:
            session.close()
    except Exception as exc:
        logger.debug("batch gauge probe failed: %s", exc)
        return 0


def refresh_observability_gauges() -> None:
    QUEUE_DEPTH.set(_redis_queue_depth())
    BATCHES_IN_PROGRESS.set(_batches_in_progress_count())


def init_sentry():
    dsn = os.environ.get("SENTRY_DSN")
    if dsn:
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=1.0
        )
