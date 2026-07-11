import pytest
import threading
from backend.modal_pool.counters import InMemoryCounters

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
