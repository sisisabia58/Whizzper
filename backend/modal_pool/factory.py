import os
from typing import Optional, Tuple

from backend.modal_pool.config import get_pool_config
from backend.modal_pool.counters import Counters, InMemoryCounters, RedisCounters
from backend.modal_pool.pool import ModalEndpointPool
from backend.modal_pool.round_robin import InMemoryRoundRobin, RedisRoundRobin, RoundRobin


def _use_in_memory_pool_state() -> bool:
    if os.environ.get("TEST_ENV") == "true":
        return True
    if os.environ.get("MODAL_POOL_IN_MEMORY") == "true":
        return True
    return not os.environ.get("REDIS_URL", "").strip()


def create_pool_state() -> Tuple[Counters, RoundRobin]:
    if _use_in_memory_pool_state():
        return InMemoryCounters(), InMemoryRoundRobin()

    import redis

    redis_url = os.environ.get("REDIS_URL", "").strip()
    client = redis.from_url(redis_url, decode_responses=True)
    client.ping()
    return RedisCounters(client), RedisRoundRobin(client)


def create_modal_pool() -> Optional[ModalEndpointPool]:
    try:
        pool_cfg = get_pool_config()
    except Exception:
        return None

    counters, round_robin = create_pool_state()
    return ModalEndpointPool(
        endpoints=pool_cfg["endpoints"],
        counters=counters,
        round_robin=round_robin,
        per_endpoint_cap=pool_cfg["per_endpoint_cap"],
        unhealthy_threshold=pool_cfg["unhealthy_threshold"],
        cooldown_seconds=pool_cfg["cooldown_seconds"],
    )


def get_max_retries() -> int:
    try:
        return get_pool_config()["max_retries"]
    except Exception:
        return 2
