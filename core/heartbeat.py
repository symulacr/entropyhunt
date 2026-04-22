from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HeartbeatStatus:
    active: set[str]
    stale: set[str]


class HeartbeatRegistry:
    __slots__ = ("_last_seen_ms", "_lock", "_stale")

    def __init__(self) -> None:
        self._last_seen_ms: dict[str, int] = {}
        self._stale: set[str] = set()
        self._lock = threading.Lock()

    def register(self, drone_id: str, *, now_ms: int) -> None:
        with self._lock:
            self._last_seen_ms[drone_id] = now_ms
            self._stale.discard(drone_id)

    def beat(self, drone_id: str, *, now_ms: int) -> None:
        self.register(drone_id, now_ms=now_ms)

    def mark_stale(self, drone_id: str) -> None:
        with self._lock:
            self._stale.add(drone_id)

    def is_stale(self, drone_id: str, *, now_ms: int, timeout_ms: int) -> bool:
        with self._lock:
            last_seen = self._last_seen_ms.get(drone_id)
            if last_seen is None:
                return False
            return now_ms - last_seen > timeout_ms or drone_id in self._stale

    def detect_stale(self, *, now_ms: int, timeout_ms: int) -> HeartbeatStatus:
        with self._lock:
            active = {
                drone_id
                for drone_id, last_seen in self._last_seen_ms.items()
                if now_ms - last_seen <= timeout_ms and drone_id not in self._stale
            }
            stale = {
                drone_id
                for drone_id, last_seen in self._last_seen_ms.items()
                if now_ms - last_seen > timeout_ms or drone_id in self._stale
            }
            self._stale = stale
        return HeartbeatStatus(active=active, stale=stale)
