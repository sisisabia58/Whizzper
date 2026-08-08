import threading

import fakeredis
import pytest

from backend.modal_pool.counters import InMemoryCounters, RedisCounters
from backend.modal_pool.round_robin import InMemoryRoundRobin, RedisRoundRobin


def test_increment_decrement_per_endpoint():
    counters = InMemoryCounters()
    assert counters.get("ep1") == 0
    assert counters.increment("ep1") == 1
    assert counters.get("ep1") == 1
    assert counters.decrement("ep1") == 0
    assert counters.get("ep1") == 0


def test_counts_are_isolated_per_endpoint():
    counters = InMemoryCounters()
    counters.increment("ep1")
    assert counters.get("ep1") == 1
    assert counters.get("ep2") == 0


def test_thread_safe_under_concurrent_updates():
    counters = InMemoryCounters()
    threads = []

    def worker():
        for _ in range(100):
            counters.increment("ep1")
            counters.decrement("ep1")

    for _ in range(10):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert counters.get("ep1") == 0


@pytest.fixture
def fake_redis():
    return fakeredis.FakeRedis(decode_responses=True)


def test_redis_counters_increment_decrement(fake_redis):
    counters = RedisCounters(fake_redis)
    ep = "https://ep1.modal.run"
    assert counters.get(ep) == 0
    assert counters.increment(ep) == 1
    assert counters.get(ep) == 1
    assert counters.decrement(ep) == 0
    assert counters.get(ep) == 0


def test_redis_counters_decrement_does_not_go_negative(fake_redis):
    counters = RedisCounters(fake_redis)
    ep = "https://ep1.modal.run"
    assert counters.decrement(ep) == 0
    assert counters.get(ep) == 0


def test_redis_counters_shared_across_instances(fake_redis):
    counters_a = RedisCounters(fake_redis)
    counters_b = RedisCounters(fake_redis)
    ep = "https://ep1.modal.run"
    counters_a.increment(ep)
    assert counters_b.get(ep) == 1
    counters_b.decrement(ep)
    assert counters_a.get(ep) == 0


def test_redis_round_robin_shared_across_instances(fake_redis):
    rr_a = RedisRoundRobin(fake_redis)
    rr_b = RedisRoundRobin(fake_redis)
    assert rr_a.pick_index(2, 2) == 0
    assert rr_b.pick_index(2, 2) == 1
    assert rr_a.pick_index(2, 2) == 0


def test_in_memory_round_robin_matches_pool_semantics():
    rr = InMemoryRoundRobin()
    p1 = rr.pick_index(2, 2)
    p2 = rr.pick_index(2, 2)
    assert {p1, p2} == {0, 1}
