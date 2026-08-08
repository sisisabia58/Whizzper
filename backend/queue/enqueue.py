"""Enqueue Celery tasks from the API with Redis health checks and clear errors."""

import os
from typing import Any, Callable

from celery import Celery


class CeleryEnqueueError(Exception):
    """Redis broker is missing or unreachable — batch/single enqueue cannot proceed."""


def _redis_url() -> str:
    return os.environ.get("REDIS_URL", "").strip()


def check_redis_broker(timeout: float = 2.0) -> None:
    """Verify REDIS_URL is set and the broker accepts a ping."""
    redis_url = _redis_url()
    if not redis_url:
        raise CeleryEnqueueError(
            "REDIS_URL is not set. Add a Redis service on Railway and reference "
            "REDIS_URL on the web and worker services (required for batch transcription)."
        )
    try:
        import redis

        client = redis.from_url(redis_url, socket_connect_timeout=timeout)
        client.ping()
    except CeleryEnqueueError:
        raise
    except Exception as exc:
        raise CeleryEnqueueError(
            f"Cannot reach Redis broker at REDIS_URL ({exc}). "
            "Ensure Redis is running and REDIS_URL uses the private Railway URL."
        ) from exc


def enqueue_task(task: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Send a fire-and-forget task to the broker; raises CeleryEnqueueError if Redis is down."""
    check_redis_broker()
    task.apply_async(args=args, kwargs=kwargs, ignore_result=True)
