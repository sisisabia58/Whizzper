import hashlib
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


def _endpoint_key(endpoint: str) -> str:
    digest = hashlib.sha256(endpoint.encode("utf-8")).hexdigest()[:16]
    return f"whizzper:modal:inflight:{digest}"


class RedisCounters:
    def __init__(self, redis_client) -> None:
        self._client = redis_client

    def _key(self, endpoint: str) -> str:
        return _endpoint_key(endpoint)

    def increment(self, endpoint: str) -> int:
        return int(self._client.incr(self._key(endpoint)))

    def decrement(self, endpoint: str) -> int:
        key = self._key(endpoint)
        current = self._client.get(key)
        if current is None or int(current) <= 0:
            self._client.set(key, 0)
            return 0
        val = int(self._client.decr(key))
        if val < 0:
            self._client.set(key, 0)
            return 0
        return val

    def get(self, endpoint: str) -> int:
        raw = self._client.get(self._key(endpoint))
        if raw is None:
            return 0
        return int(raw)
