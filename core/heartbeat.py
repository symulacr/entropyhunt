from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HeartbeatStatus:
    active: set[str]
    stale: set[str]


class HeartbeatRegistry:
    def __init__(self) -> None:
        self._last_seen_ms: dict[str, int] = {}
        self._stale: set[str] = set()

    def beat(self, drone_id: str, *, now_ms: int) -> None:
        self._last_seen_ms[drone_id] = now_ms
        self._stale.discard(drone_id)

    def mark_stale(self, drone_id: str) -> None:
        self._stale.add(drone_id)

    def detect_stale(self, *, now_ms: int, timeout_ms: int) -> HeartbeatStatus:
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
