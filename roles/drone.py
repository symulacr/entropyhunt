
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, TypeGuard, get_args

if TYPE_CHECKING:
    from core.certainty import Coordinate

DroneStatus = Literal[
    "idle",
    "computing",
    "claiming",
    "claim_won",
    "claim_lost",
    "transiting",
    "searching",
    "stale",
]

VALID_DRONE_STATUSES: frozenset[DroneStatus] = frozenset(get_args(DroneStatus))

def is_drone_status(value: str) -> TypeGuard[DroneStatus]:
    return value in VALID_DRONE_STATUSES

def spread_starting_position(drone_id: str, peer_ids: list[str], grid: int) -> Coordinate:
    if grid <= 1:
        return (0, 0)
    ordered_ids = sorted(dict.fromkeys(peer_ids or [drone_id]))
    try:
        index = ordered_ids.index(drone_id)
    except ValueError:
        index = 0
    max_idx = grid - 1
    perimeter: list[Coordinate] = [(x, 0) for x in range(grid)]
    perimeter.extend((max_idx, y) for y in range(1, grid))
    perimeter.extend((x, max_idx) for x in range(max_idx - 1, -1, -1))
    perimeter.extend((0, y) for y in range(max_idx - 1, 0, -1))
    step = max(1, len(perimeter) // max(1, len(ordered_ids)))
    return perimeter[(index * step) % len(perimeter)]

@dataclass(slots=True)
class DroneState:

    drone_id: str
    position: Coordinate
    status: DroneStatus = "idle"
    role: str = "scout"
    target_cell: Coordinate | None = None
    claimed_cell: Coordinate | None = None
    subzone: str | None = None
    alive: bool = True
    reachable: bool = True
    searched_cells: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def set_assignment(self, coordinate: Coordinate, *, subzone: str | None = None) -> None:
        with self._lock:
            self.target_cell = coordinate
            self.claimed_cell = coordinate
            self.subzone = subzone
            self.status = "transiting" if self.position != coordinate else "searching"

    def clear_assignment(self) -> None:
        with self._lock:
            self.target_cell = None
            self.claimed_cell = None
            self.subzone = None
            self.status = "idle" if self.alive else "stale"

    def mark_stale(self) -> None:
        with self._lock:
            self.alive = False
            self.reachable = False
            self.status = "stale"
            self.target_cell = None
            self.claimed_cell = None
            self.subzone = None

    def revive(self, coordinate: Coordinate) -> None:
        with self._lock:
            self.alive = True
            self.reachable = True
            self.position = coordinate
            self.status = "idle"
            self.target_cell = None
            self.claimed_cell = None
            self.subzone = None

    def step_towards_target(self) -> None:
        with self._lock:
            if not self.alive or self.target_cell is None:
                return
            x, y = self.position
            tx, ty = self.target_cell
            if x != tx:
                x += 1 if tx > x else -1
            elif y != ty:
                y += 1 if ty > y else -1
            self.position = (x, y)
            self.status = "searching" if self.position == self.target_cell else "transiting"
