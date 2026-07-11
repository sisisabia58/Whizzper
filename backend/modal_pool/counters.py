import threading
from typing import Dict, Protocol

class Counters(Protocol):
    def increment(self, endpoint: str) -> int:
        ...
    def decrement(self, endpoint: str) -> int:
        ...
    def get(self, endpoint: str) -> int:
        ...

class InMemoryCounters:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: Dict[str, int] = {}

    def increment(self, endpoint: str) -> int:
        with self._lock:
            val = self._counts.get(endpoint, 0) + 1
            self._counts[endpoint] = val
            return val

    def decrement(self, endpoint: str) -> int:
        with self._lock:
            val = self._counts.get(endpoint, 0) - 1
            if val < 0:
                val = 0
            self._counts[endpoint] = val
            return val

    def get(self, endpoint: str) -> int:
        with self._lock:
            return self._counts.get(endpoint, 0)
