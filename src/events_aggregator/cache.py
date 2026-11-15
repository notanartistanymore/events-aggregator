import threading
import time
from uuid import UUID


class SeatsCache:
    def __init__(self, ttl: int = 30):
        self.ttl = ttl
        self._data: dict[UUID, tuple[float, list[str]]] = {}
        self._lock = threading.Lock()

    def get(self, event_id: UUID) -> list[str] | None:
        with self._lock:
            item = self._data.get(event_id)
            if item and item[0] > time.monotonic():
                return list(item[1])
            self._data.pop(event_id, None)
        return None

    def set(self, event_id: UUID, seats: list[str]) -> None:
        with self._lock:
            self._data[event_id] = (time.monotonic() + self.ttl, list(seats))

    def invalidate(self, event_id: UUID) -> None:
        with self._lock:
            self._data.pop(event_id, None)
