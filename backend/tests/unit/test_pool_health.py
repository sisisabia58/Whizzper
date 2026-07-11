import time
import pytest
from backend.modal_pool.pool import ModalEndpointPool
from backend.modal_pool.counters import InMemoryCounters

def test_marks_unhealthy_after_threshold_failures():
    endpoints = ["https://ep1.modal.run", "https://ep2.modal.run"]
    counters = InMemoryCounters()
    pool = ModalEndpointPool(endpoints=endpoints, counters=counters, unhealthy_threshold=3, cooldown_seconds=60)
    
    # 3 failures on ep1
    pool.record_failure("https://ep1.modal.run")
    pool.record_failure("https://ep1.modal.run")
    pool.record_failure("https://ep1.modal.run")
    
    # ep1 should be excluded. Only ep2 should be healthy.
    assert pool.healthy_endpoints() == ["https://ep2.modal.run"]
    assert pool.pick() == "https://ep2.modal.run"

def test_endpoint_restored_after_cooldown(monkeypatch):
    endpoints = ["https://ep1.modal.run"]
    counters = InMemoryCounters()
    pool = ModalEndpointPool(endpoints=endpoints, counters=counters, unhealthy_threshold=1, cooldown_seconds=2)
    
    pool.record_failure("https://ep1.modal.run")
    assert pool.healthy_endpoints() == []
    
    time.sleep(2.5) # Wait for cooldown to expire
    assert pool.pick() == "https://ep1.modal.run"

def test_success_resets_failure_count():
    endpoints = ["https://ep1.modal.run"]
    counters = InMemoryCounters()
    pool = ModalEndpointPool(endpoints=endpoints, counters=counters, unhealthy_threshold=2)
    
    pool.record_failure("https://ep1.modal.run")
    pool.record_success("https://ep1.modal.run")
    pool.record_failure("https://ep1.modal.run")
    
    # Since it was reset by success, 1 failure does not exceed threshold 2
    assert pool.healthy_endpoints() == ["https://ep1.modal.run"]
