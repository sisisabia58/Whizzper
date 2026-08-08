import os

import fakeredis
import pytest

from backend.modal_pool.factory import create_pool_state
from backend.modal_pool.counters import InMemoryCounters, RedisCounters
from backend.modal_pool.round_robin import InMemoryRoundRobin, RedisRoundRobin
from backend.modal_pool.pool import ModalEndpointPool


def test_create_pool_state_uses_in_memory_when_test_env():
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("TEST_ENV", "true")
        mp.delenv("REDIS_URL", raising=False)
        counters, rr = create_pool_state()
        assert isinstance(counters, InMemoryCounters)
        assert isinstance(rr, InMemoryRoundRobin)


def test_create_pool_state_uses_redis_when_configured():
    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server, decode_responses=True)
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("TEST_ENV", raising=False)
        mp.setenv("REDIS_URL", "redis://localhost:6379/0")

        import redis

        mp.setattr(redis, "from_url", lambda url, **kwargs: client)

        counters, rr = create_pool_state()
        assert isinstance(counters, RedisCounters)
        assert isinstance(rr, RedisRoundRobin)


def test_parallel_picks_spread_across_endpoints_with_shared_redis_state():
    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server, decode_responses=True)
    endpoints = ["https://ep1.modal.run", "https://ep2.modal.run"]
    counters = RedisCounters(client)
    round_robin = RedisRoundRobin(client)
    pool_a = ModalEndpointPool(
        endpoints=endpoints,
        counters=counters,
        round_robin=round_robin,
        per_endpoint_cap=1,
    )
    pool_b = ModalEndpointPool(
        endpoints=endpoints,
        counters=counters,
        round_robin=round_robin,
        per_endpoint_cap=1,
    )

    # One inflight on ep1 — both workers should prefer ep2
    counters.increment(endpoints[0])

    assert pool_a.pick() == endpoints[1]
    assert pool_b.pick() == endpoints[1]

    counters.increment(endpoints[1])
    assert pool_a.pick() is None
    assert pool_b.pick() is None
