from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class DroneRecord:
    drone_id: str
    x: int = 0
    y: int = 0
    tx: int = -1
    ty: int = -1
    status: str = "booting"
    alive: bool = True
    reachable: bool = True
    searched_cells: int = 0
    last_heartbeat_ms: int = 0


@dataclass(slots=True)
class GridRecord:
    size: int
    certainty: dict[tuple[int, int], float] = field(default_factory=dict)


@dataclass(slots=True)
class EventRecord:
    t_ms: int
    event_type: str
    msg: str


@dataclass(slots=True)
class ClaimRecord:
    claim_id: str
    drone_id: str
    x: int
    y: int
    timestamp_ms: int


@dataclass(slots=True)
class OperatorState:
    drone_count: int
    grid: GridRecord
    drones: dict[str, DroneRecord] = field(default_factory=dict)
    claims: dict[str, ClaimRecord] = field(default_factory=dict)
    owners: dict[tuple[int, int], str] = field(default_factory=dict)
    events: list[EventRecord] = field(default_factory=list)
    survivor_found: bool = False

    @classmethod
    def create(cls, *, drone_count: int, grid_size: int) -> "OperatorState":
        return cls(drone_count=drone_count, grid=GridRecord(size=grid_size))
