from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.certainty_map import Coordinate

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


@dataclass(slots=True)
class DroneState:
    drone_id: str
    position: Coordinate
    status: DroneStatus = "idle"
    target_cell: Coordinate | None = None
    claimed_cell: Coordinate | None = None
    subzone: str | None = None
    alive: bool = True
    reachable: bool = True
    searched_cells: int = 0

    def set_assignment(self, coordinate: Coordinate, *, subzone: str | None = None) -> None:
        self.target_cell = coordinate
        self.claimed_cell = coordinate
        self.subzone = subzone
        self.status = "transiting" if self.position != coordinate else "searching"

    def clear_assignment(self) -> None:
        self.target_cell = None
        self.claimed_cell = None
        self.subzone = None
        self.status = "idle" if self.alive else "stale"

    def mark_stale(self) -> None:
        self.alive = False
        self.reachable = False
        self.status = "stale"
        self.target_cell = None
        self.claimed_cell = None
        self.subzone = None

    def revive(self, coordinate: Coordinate) -> None:
        self.alive = True
        self.reachable = True
        self.position = coordinate
        self.status = "idle"
        self.target_cell = None
        self.claimed_cell = None
        self.subzone = None

    def step_towards_target(self) -> None:
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
