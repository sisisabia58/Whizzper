import pytest
from backend.modal_pool.pool import ModalEndpointPool
from backend.modal_pool.counters import InMemoryCounters

def test_picks_endpoint_with_fewest_inflight():
    endpoints = ["https://ep1.modal.run", "https://ep2.modal.run"]
    counters = InMemoryCounters()
    pool = ModalEndpointPool(endpoints=endpoints, counters=counters, per_endpoint_cap=10)
    
    counters.increment("https://ep1.modal.run") # ep1 has 1 in-flight
    # ep2 has 0 in-flight. So pick should choose ep2.
    assert pool.pick() == "https://ep2.modal.run"

def test_round_robin_breaks_ties():
    endpoints = ["https://ep1.modal.run", "https://ep2.modal.run"]
    counters = InMemoryCounters()
    pool = ModalEndpointPool(endpoints=endpoints, counters=counters, per_endpoint_cap=10)
    
    # Both have 0 in-flight. First pick: index 0, Second pick: index 1
    p1 = pool.pick()
    p2 = pool.pick()
    assert {p1, p2} == {"https://ep1.modal.run", "https://ep2.modal.run"}

def test_skips_endpoints_at_cap():
    endpoints = ["https://ep1.modal.run", "https://ep2.modal.run"]
    counters = InMemoryCounters()
    pool = ModalEndpointPool(endpoints=endpoints, counters=counters, per_endpoint_cap=1)
    
    # Fill ep1 to cap
    counters.increment("https://ep1.modal.run")
    
    # ep1 is at cap (1). ep2 is free (0).
    assert pool.pick() == "https://ep2.modal.run"
    
    # Fill ep2 to cap
    counters.increment("https://ep2.modal.run")
    
    # Both are at cap. Pick should return None
    assert pool.pick() is None
