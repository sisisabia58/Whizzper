import pytest
from unittest.mock import MagicMock, patch
from backend.modal_pool.pool import ModalEndpointPool
from backend.modal_pool.counters import InMemoryCounters

def test_failover_loop_executes_on_endpoints():
    endpoints = ["https://ep-fail.modal.run", "https://ep-success.modal.run"]
    counters = InMemoryCounters()
    pool = ModalEndpointPool(endpoints=endpoints, counters=counters, unhealthy_threshold=3)

    executed_endpoints = []
    
    def mock_run_on_endpoint(endpoint_url):
        executed_endpoints.append(endpoint_url)
        if "fail" in endpoint_url:
            pool.record_failure(endpoint_url)
            raise RuntimeError("Simulated Modal Failure")
        pool.record_success(endpoint_url)
        return "success_srt"

    max_retries = 2
    success = False
    result = None
    
    for attempt in range(max_retries + 1):
        try:
            with pool.acquire() as ep:
                result = mock_run_on_endpoint(ep)
                success = True
                break
        except Exception:
            continue

    assert success is True
    assert result == "success_srt"
    assert executed_endpoints == ["https://ep-fail.modal.run", "https://ep-success.modal.run"]
