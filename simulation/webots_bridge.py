
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.certainty import Coordinate
    from roles.drone import DroneState

@dataclass(frozen=True, slots=True)
class ExternalDroneState:

    drone_id: str
    position: Coordinate
    reachable: bool = True

@dataclass(frozen=True, slots=True)
class MovementCommand:

    drone_id: str
    target: Coordinate | None
    status: str

@dataclass(frozen=True, slots=True)
class BridgeSnapshot:

    drones: tuple[ExternalDroneState, ...]
    tick_seconds: int

class WebotsBridgeAdapter:

    def apply_snapshot(self, drones: list[DroneState], snapshot: BridgeSnapshot) -> None:
        by_id = {drone.drone_id: drone for drone in drones}
        for external in snapshot.drones:
            drone = by_id.get(external.drone_id)
            if drone is None:
                continue
            drone.position = external.position
            drone.reachable = external.reachable and drone.alive
            if not drone.reachable and drone.alive:
                drone.status = "stale"

    def build_commands(self, drones: list[DroneState]) -> list[MovementCommand]:
        return [
            MovementCommand(
                drone_id=drone.drone_id,
                target=drone.target_cell,
                status=drone.status,
            )
            for drone in drones
            if drone.alive
        ]

def build_bridge_snapshot(drones: list[DroneState], *, tick_seconds: int) -> dict[str, Any]:
    snapshot = BridgeSnapshot(
        drones=tuple(
            ExternalDroneState(
                drone_id=drone.drone_id,
                position=drone.position,
                reachable=drone.reachable,
            )
            for drone in drones
        ),
        tick_seconds=tick_seconds,
    )
    return {
        "tick_seconds": snapshot.tick_seconds,
        "drones": [asdict(drone) for drone in snapshot.drones],
        "commands": [asdict(command) for command in WebotsBridgeAdapter().build_commands(drones)],
    }
