import os
from typing import Optional


def check_redis_health() -> Optional[bool]:
    """Ping Redis when REDIS_URL is set. Returns None if Redis is not configured."""
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        return None
    try:
        import redis

        client = redis.from_url(redis_url, socket_connect_timeout=1)
        client.ping()
        return True
    except Exception:
        return False


def health_status_code(database_ok: bool) -> int:
    """Railway liveness: only the database is required for a passing healthcheck."""
    return 200 if database_ok else 503


def health_status_label(database_ok: bool, redis_ok: Optional[bool]) -> str:
    if not database_ok:
        return "unhealthy"
    if redis_ok is False:
        return "degraded"
    return "ok"
