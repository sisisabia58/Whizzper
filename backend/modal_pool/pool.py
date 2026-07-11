import time
import threading
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from backend.modal_pool.counters import Counters

class ModalEndpointPool:
    def __init__(
        self,
        endpoints: List[str],
        counters: Counters,
        per_endpoint_cap: int = 10,
        unhealthy_threshold: int = 3,
        cooldown_seconds: int = 60,
    ) -> None:
        self.endpoints = endpoints
        self.counters = counters
        self.per_endpoint_cap = per_endpoint_cap
        self.unhealthy_threshold = unhealthy_threshold
        self.cooldown_seconds = cooldown_seconds
        
        self._lock = threading.Lock()
        self._rr_index = 0
        
        # Health tracking
        self._consecutive_failures: Dict[str, int] = {ep: 0 for ep in endpoints}
        self._unhealthy_since: Dict[str, float] = {}

    def pick(self) -> Optional[str]:
        with self._lock:
            # Filter to healthy endpoints (considering cooldown reset)
            now = time.time()
            active_endpoints = []
            
            for ep in self.endpoints:
                is_healthy = True
                if ep in self._unhealthy_since:
                    since = self._unhealthy_since[ep]
                    if now - since >= self.cooldown_seconds:
                        # Reset failure status after cooldown
                        self._consecutive_failures[ep] = 0
                        del self._unhealthy_since[ep]
                    else:
                        is_healthy = False
                if is_healthy:
                    active_endpoints.append(ep)
                    
            if not active_endpoints:
                return None

            # Get in-flight count for candidates
            loads = [(ep, self.counters.get(ep)) for ep in active_endpoints]
            
            # Filter candidates under cap
            candidates = [el for el in loads if el[1] < self.per_endpoint_cap]
            if not candidates:
                return None
                
            # Find the minimum load
            min_load = min(el[1] for el in candidates)
            best_candidates = [el[0] for el in candidates if el[1] == min_load]
            
            # Tie-break by round-robin over the subset of best candidates
            # Choose from best_candidates that matches the round robin index sequence
            chosen = best_candidates[self._rr_index % len(best_candidates)]
            self._rr_index = (self._rr_index + 1) % len(self.endpoints)
            return chosen

    @contextmanager
    def acquire(self):
        endpoint = self.pick()
        if not endpoint:
            raise RuntimeError("No healthy endpoints available or capacity limit exceeded.")
            
        self.counters.increment(endpoint)
        try:
            yield endpoint
        finally:
            self.counters.decrement(endpoint)

