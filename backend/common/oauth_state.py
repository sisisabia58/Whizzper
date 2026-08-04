import threading
import time
import uuid
from typing import Dict

_states: Dict[str, float] = {}
_lock = threading.Lock()
TTL_SECONDS = 600


def create_state() -> str:
    state = str(uuid.uuid4())
    with _lock:
        _cleanup_expired()
        _states[state] = time.time()
    return state


def validate_state(state: str) -> bool:
    with _lock:
        _cleanup_expired()
        if state not in _states:
            return False
        del _states[state]
        return True


def _cleanup_expired() -> None:
    now = time.time()
    expired = [key for key, created in _states.items() if now - created > TTL_SECONDS]
    for key in expired:
        del _states[key]
