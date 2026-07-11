import pytest
from backend.modal_pool.pool import ModalEndpointPool
from backend.modal_pool.counters import InMemoryCounters

def test_acquire_increments_and_release_decrements():
    endpoints = ["https://ep1.modal.run"]
    counters = InMemoryCounters()
    pool = ModalEndpointPool(endpoints=endpoints, counters=counters, per_endpoint_cap=10)
    
    with pool.acquire() as endpoint:
        assert endpoint == "https://ep1.modal.run"
        assert counters.get(endpoint) == 1
        
    assert counters.get("https://ep1.modal.run") == 0

def test_release_on_exception_still_decrements():
    endpoints = ["https://ep1.modal.run"]
    counters = InMemoryCounters()
    pool = ModalEndpointPool(endpoints=endpoints, counters=counters, per_endpoint_cap=10)
    
    try:
        with pool.acquire() as endpoint:
            assert counters.get(endpoint) == 1
            raise RuntimeError("Inference failed")
    except RuntimeError:
        pass
        
    assert counters.get("https://ep1.modal.run") == 0
