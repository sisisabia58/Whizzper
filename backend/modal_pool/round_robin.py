import threading
from typing import Protocol


class RoundRobin(Protocol):
    def pick_index(self, num_choices: int, cycle_length: int) -> int:
        """Return choice index in [0, num_choices) and advance state modulo cycle_length."""
        ...


class InMemoryRoundRobin:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._index = 0

    def pick_index(self, num_choices: int, cycle_length: int) -> int:
        with self._lock:
            idx = self._index % num_choices
            self._index = (self._index + 1) % cycle_length
            return idx


class RedisRoundRobin:
    RR_KEY = "whizzper:modal:rr_index"

    def __init__(self, redis_client) -> None:
        self._client = redis_client

    def pick_index(self, num_choices: int, cycle_length: int) -> int:
        val = self._client.incr(self.RR_KEY)
        base = (val - 1) % cycle_length
        return base % num_choices
