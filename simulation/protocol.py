
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from roles.drone import DroneStatus, is_drone_status

if TYPE_CHECKING:
    from collections.abc import Sequence

    from core.certainty import Coordinate

@dataclass(frozen=True, slots=True)
class PeerEndpoint:

    peer_id: str
    host: str
    port: int

@dataclass(frozen=True, slots=True)
class HeartbeatPayload:

    drone_id: str
    position: Coordinate
    peer_status: str = "HEALTHY"


@dataclass(frozen=True, slots=True)
class RejoinPayload:

    drone_id: str
    recovered_at_ms: int

@dataclass(frozen=True, slots=True)
class ClaimPayload:

    claim_id: str
    drone_id: str
    cell: Coordinate
    position: Coordinate
    timestamp_ms: int

@dataclass(frozen=True, slots=True)
class AssignmentPayload:

    drone_id: str
    cell: Coordinate
    reason: str
    subzone: str | None = None

@dataclass(frozen=True, slots=True)
class ConsensusRoundPayload:

    round_id: int
    cell: Coordinate
    assignments: tuple[AssignmentPayload, ...]
    rationale: str
    contest_id: str | None = None
    released_by: str | None = None

@dataclass(frozen=True, slots=True)
class CertaintyUpdatePayload:

    updated_by: str
    cell: Coordinate
    certainty: float

@dataclass(frozen=True, slots=True)
class SurvivorPayload:

    drone_id: str
    cell: Coordinate
    confidence: float

@dataclass(frozen=True, slots=True)
class DroneStatePayload:

    drone_id: str
    position: Coordinate
    target: Coordinate | None
    status: DroneStatus
    alive: bool
    reachable: bool
    claimed_cell: Coordinate | None
    searched_cells: int

def heartbeat_topic(drone_id: str) -> str:
    return f"swarm/heartbeat/{drone_id}"


def drone_state_topic(drone_id: str) -> str:
    return f"swarm/drone_state/{drone_id}"


def consensus_round_topic(round_id: int) -> str:
    return f"swarm/consensus_result/{round_id}"


def survivor_ack_topic(drone_id: str) -> str:
    return f"swarm/survivor_found_ack/{drone_id}"


def rejoin_topic(drone_id: str) -> str:
    return f"swarm/rejoin/{drone_id}"


def _coordinate(value: Sequence[float | int | str]) -> Coordinate:
    x, y = value
    return (int(x), int(y))


def make_heartbeat_payload(
    *, drone_id: str, position: Coordinate, peer_status: str = "HEALTHY",
) -> dict[str, Any]:
    return asdict(HeartbeatPayload(drone_id=drone_id, position=position, peer_status=peer_status))


def make_rejoin_payload(*, drone_id: str, recovered_at_ms: int) -> dict[str, Any]:
    return asdict(RejoinPayload(drone_id=drone_id, recovered_at_ms=recovered_at_ms))

def make_claim_payload(
    payload: ClaimPayload | None = None,
    *,
    claim_id: str | None = None,
    drone_id: str | None = None,
    cell: Coordinate | None = None,
    position: Coordinate | None = None,
    timestamp_ms: int | None = None,
) -> dict[str, Any]:
    if payload is None:
        assert claim_id is not None
        assert drone_id is not None
        assert cell is not None
        assert position is not None
        assert timestamp_ms is not None
        payload = ClaimPayload(
            claim_id=claim_id,
            drone_id=drone_id,
            cell=cell,
            position=position,
            timestamp_ms=timestamp_ms,
        )
    return asdict(payload)

def make_assignment_payload(
    *,
    drone_id: str,
    cell: Coordinate,
    reason: str,
    subzone: str | None = None,
) -> dict[str, Any]:
    return asdict(AssignmentPayload(drone_id=drone_id, cell=cell, reason=reason, subzone=subzone))

def make_consensus_round_payload(
    *,
    round_id: int,
    cell: Coordinate,
    assignments: list[dict[str, Any]],
    rationale: str,
    contest_id: str | None = None,
    released_by: str | None = None,
) -> dict[str, Any]:
    return {
        "round_id": round_id,
        "cell": list(cell),
        "assignments": assignments,
        "rationale": rationale,
        "contest_id": contest_id,
        "released_by": released_by,
    }

def make_certainty_payload(
    *,
    updated_by: str,
    cell: Coordinate,
    certainty: float,
) -> dict[str, Any]:
    return asdict(CertaintyUpdatePayload(updated_by=updated_by, cell=cell, certainty=certainty))

def make_survivor_payload(*, drone_id: str, cell: Coordinate, confidence: float) -> dict[str, Any]:
    return asdict(SurvivorPayload(drone_id=drone_id, cell=cell, confidence=confidence))

def make_drone_state_payload(payload: DroneStatePayload) -> dict[str, Any]:
    return asdict(payload)

def parse_peer_endpoint(value: str) -> PeerEndpoint:
    peer_id: str | None = None
    target = value
    if "@" in value:
        peer_id, target = value.split("@", maxsplit=1)
    host, port = target.rsplit(":", maxsplit=1)
    return PeerEndpoint(peer_id=peer_id or "", host=host, port=int(port))

def parse_claim_payload(payload: dict[str, Any]) -> ClaimPayload:
    return ClaimPayload(
        claim_id=str(payload["claim_id"]),
        drone_id=str(payload["drone_id"]),
        cell=_coordinate(payload["cell"]),
        position=_coordinate(payload["position"]),
        timestamp_ms=int(payload["timestamp_ms"]),
    )

def parse_consensus_round_payload(payload: dict[str, Any]) -> ConsensusRoundPayload:
    assignments = tuple(
        AssignmentPayload(
            drone_id=str(item["drone_id"]),
            cell=_coordinate(item["cell"]),
            reason=str(item["reason"]),
            subzone=item.get("subzone"),
        )
        for item in payload.get("assignments", [])
    )
    return ConsensusRoundPayload(
        round_id=int(payload["round_id"]),
        cell=_coordinate(payload["cell"]),
        assignments=assignments,
        rationale=str(payload["rationale"]),
        contest_id=str(payload["contest_id"]) if payload.get("contest_id") is not None else None,
        released_by=str(payload["released_by"]) if payload.get("released_by") is not None else None,
    )

def parse_certainty_payload(payload: dict[str, Any]) -> CertaintyUpdatePayload:
    return CertaintyUpdatePayload(
        updated_by=str(payload["updated_by"]),
        cell=_coordinate(payload["cell"]),
        certainty=float(payload["certainty"]),
    )

def parse_survivor_payload(payload: dict[str, Any]) -> SurvivorPayload:
    return SurvivorPayload(
        drone_id=str(payload["drone_id"]),
        cell=_coordinate(payload["cell"]),
        confidence=float(payload["confidence"]),
    )

def parse_drone_state_payload(payload: dict[str, Any]) -> DroneStatePayload:
    raw_status = str(payload["status"])
    status: DroneStatus = raw_status if is_drone_status(raw_status) else "idle"
    return DroneStatePayload(
        drone_id=str(payload["drone_id"]),
        position=_coordinate(payload["position"]),
        target=_coordinate(payload["target"]) if payload.get("target") is not None else None,
        status=status,
        alive=bool(payload["alive"]),
        reachable=bool(payload["reachable"]),
        claimed_cell=_coordinate(payload["claimed_cell"])
        if payload.get("claimed_cell") is not None
        else None,
        searched_cells=int(payload.get("searched_cells", 0)),
    )
