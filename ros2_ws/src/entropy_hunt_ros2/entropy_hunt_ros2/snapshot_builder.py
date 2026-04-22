from __future__ import annotations

from dataclasses import asdict
from typing import Any, TypedDict

from .operator_state import ClaimRecord, DroneRecord, EventRecord, OperatorState

VISITED_THRESHOLD = 0.5
COMPLETED_THRESHOLD = 0.95


class AssignmentPayload(TypedDict):
    drone_id: str
    x: int
    y: int
    reason: str


def _ensure_drone(state: OperatorState, drone_id: str) -> DroneRecord:
    if drone_id not in state.drones:
        state.drones[drone_id] = DroneRecord(drone_id=drone_id)
    return state.drones[drone_id]


def _owner_index(drone_id: str) -> int:
    suffix = drone_id.rsplit("_", maxsplit=1)[-1]
    return int(suffix) - 1 if suffix.isdigit() else -1


def apply_drone_state(
    state: OperatorState,
    *,
    drone_id: str,
    x: int,
    y: int,
    tx: int,
    ty: int,
    status: str,
    alive: bool,
    reachable: bool,
    searched_cells: int,
    altitude_m: float = 0.0,
    heading_deg: float = 0.0,
    battery_pct: float = 100.0,
    flight_mode: str = "UNKNOWN",
) -> None:
    drone = _ensure_drone(state, drone_id)
    drone.x = x
    drone.y = y
    drone.tx = tx
    drone.ty = ty
    drone.status = status
    drone.alive = alive
    drone.reachable = reachable
    drone.searched_cells = searched_cells
    drone.altitude_m = altitude_m
    drone.heading_deg = heading_deg
    drone.battery_pct = battery_pct
    drone.flight_mode = flight_mode


def apply_heartbeat(
    state: OperatorState,
    *,
    drone_id: str,
    timestamp_ms: int,
    alive: bool,
    reachable: bool,
) -> None:
    drone = _ensure_drone(state, drone_id)
    drone.last_heartbeat_ms = timestamp_ms
    drone.alive = alive
    drone.reachable = reachable


def apply_certainty_update(state: OperatorState, *, x: int, y: int, certainty: float) -> None:
    state.grid.certainty[(x, y)] = float(certainty)


def apply_claim(
    state: OperatorState,
    *,
    claim_id: str,
    drone_id: str,
    x: int,
    y: int,
    timestamp_ms: int,
) -> None:
    state.claims[claim_id] = ClaimRecord(
        claim_id=claim_id,
        drone_id=drone_id,
        x=x,
        y=y,
        timestamp_ms=timestamp_ms,
    )
    append_event(
        state,
        event_type="claim",
        msg=f"{drone_id} claimed [{x},{y}]",
        timestamp_ms=timestamp_ms,
    )


def apply_consensus_result(
    state: OperatorState,
    *,
    contest_id: str,
    x: int,
    y: int,
    assignments: list[AssignmentPayload],
    rationale: str,
    timestamp_ms: int,
) -> None:
    for assignment in assignments:
        drone_id = str(assignment["drone_id"])
        state.owners[(int(assignment["x"]), int(assignment["y"]))] = drone_id
    append_event(
        state,
        event_type="consensus",
        msg=f"{contest_id} @ [{x},{y}] {rationale}",
        timestamp_ms=timestamp_ms,
    )


def apply_survivor_found(
    state: OperatorState,
    *,
    drone_id: str,
    x: int,
    y: int,
    confidence: float,
    timestamp_ms: int,
) -> None:
    state.survivor_found = True
    state.events.append(
        EventRecord(
            t_ms=timestamp_ms,
            event_type="survivor_found",
            msg=f"{drone_id} confirmed survivor at [{x},{y}] c={confidence:.2f}",
        ),
    )


def append_event(state: OperatorState, *, event_type: str, msg: str, timestamp_ms: int) -> None:
    state.events.append(EventRecord(t_ms=timestamp_ms, event_type=event_type, msg=msg))
    del state.events[:-20]


def build_snapshot(
    state: OperatorState,
    *,
    source_mode: str = "live",
    mesh_mode: str = "ros2",
    elapsed_seconds: int = 0,
) -> dict[str, Any]:
    total_cells = max(1, state.grid.size * state.grid.size)
    visited = sum(1 for certainty in state.grid.certainty.values() if certainty > VISITED_THRESHOLD)
    completed = sum(
        1 for certainty in state.grid.certainty.values() if certainty >= COMPLETED_THRESHOLD
    )
    avg_entropy_proxy = (
        0.0
        if not state.grid.certainty
        else sum(abs(0.5 - c) for c in state.grid.certainty.values()) / len(state.grid.certainty)
    )
    grid_rows = [
        [
            {
                "certainty": round(state.grid.certainty.get((x, y), 0.5), 3),
                "owner": (_owner_index(state.owners[(x, y)]) if (x, y) in state.owners else -1),
            }
            for x in range(state.grid.size)
        ]
        for y in range(state.grid.size)
    ]
    drones = [asdict(drone) for _, drone in sorted(state.drones.items())]
    return {
        "t": elapsed_seconds,
        "stats": {
            "coverage": round(visited / total_cells, 3),
            "coverage_completed": round(completed / total_cells, 3),
            "avg_entropy": round(avg_entropy_proxy, 3),
            "auctions": sum(
                1 for event in state.events if event.event_type in {"auction", "claim"}
            ),
            "dropouts": sum(1 for drone in state.drones.values() if not drone.reachable),
            "consensus_rounds": sum(1 for event in state.events if event.event_type == "consensus"),
            "elapsed": elapsed_seconds,
        },
        "config": {
            "source_mode": source_mode,
            "mesh_mode": mesh_mode,
            "grid_size": state.grid.size,
            "drone_count": state.drone_count,
        },
        "grid": grid_rows,
        "drones": drones,
        "events": [asdict(event) for event in state.events[-20:]],
        "survivor_found": state.survivor_found,
    }
