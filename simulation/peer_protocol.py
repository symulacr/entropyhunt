from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from core.certainty_map import Coordinate
from core.mesh import MeshEnvelope


@dataclass(frozen=True, slots=True)
class PeerEndpoint:
    peer_id: str | None
    host: str
    port: int


@dataclass(frozen=True, slots=True)
class HeartbeatPayload:
    drone_id: str
    position: Coordinate


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
class BftRoundPayload:
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
    status: str
    alive: bool
    reachable: bool
    claimed_cell: Coordinate | None
    searched_cells: int


def heartbeat_topic(drone_id: str) -> str:
    return f"swarm/heartbeat/{drone_id}"


def drone_state_topic(drone_id: str) -> str:
    return f"swarm/drone_state/{drone_id}"


def bft_round_topic(round_id: int) -> str:
    return f"swarm/bft_result/{round_id}"


def survivor_ack_topic(drone_id: str) -> str:
    return f"swarm/survivor_found_ack/{drone_id}"


def _coordinate(value: Any) -> Coordinate:
    x, y = value
    return (int(x), int(y))


def make_heartbeat_payload(*, drone_id: str, position: Coordinate) -> dict[str, Any]:
    return asdict(HeartbeatPayload(drone_id=drone_id, position=position))


def make_claim_payload(
    *,
    claim_id: str,
    drone_id: str,
    cell: Coordinate,
    position: Coordinate,
    timestamp_ms: int,
) -> dict[str, Any]:
    return asdict(
        ClaimPayload(
            claim_id=claim_id,
            drone_id=drone_id,
            cell=cell,
            position=position,
            timestamp_ms=timestamp_ms,
        )
    )


def make_assignment_payload(
    *,
    drone_id: str,
    cell: Coordinate,
    reason: str,
    subzone: str | None = None,
) -> dict[str, Any]:
    return asdict(AssignmentPayload(drone_id=drone_id, cell=cell, reason=reason, subzone=subzone))


def make_bft_round_payload(
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


def make_certainty_payload(*, updated_by: str, cell: Coordinate, certainty: float) -> dict[str, Any]:
    return asdict(CertaintyUpdatePayload(updated_by=updated_by, cell=cell, certainty=certainty))


def make_survivor_payload(*, drone_id: str, cell: Coordinate, confidence: float) -> dict[str, Any]:
    return asdict(SurvivorPayload(drone_id=drone_id, cell=cell, confidence=confidence))


def make_drone_state_payload(
    *,
    drone_id: str,
    position: Coordinate,
    target: Coordinate | None,
    status: str,
    alive: bool,
    reachable: bool,
    claimed_cell: Coordinate | None,
    searched_cells: int,
) -> dict[str, Any]:
    return asdict(
        DroneStatePayload(
            drone_id=drone_id,
            position=position,
            target=target,
            status=status,
            alive=alive,
            reachable=reachable,
            claimed_cell=claimed_cell,
            searched_cells=searched_cells,
        )
    )


def parse_peer_endpoint(value: str) -> PeerEndpoint:
    peer_id: str | None = None
    target = value
    if "@" in value:
        peer_id, target = value.split("@", maxsplit=1)
    host, port = target.rsplit(":", maxsplit=1)
    return PeerEndpoint(peer_id=peer_id or None, host=host, port=int(port))


def parse_claim_payload(payload: dict[str, Any]) -> ClaimPayload:
    return ClaimPayload(
        claim_id=str(payload["claim_id"]),
        drone_id=str(payload["drone_id"]),
        cell=_coordinate(payload["cell"]),
        position=_coordinate(payload["position"]),
        timestamp_ms=int(payload["timestamp_ms"]),
    )


def parse_bft_round_payload(payload: dict[str, Any]) -> BftRoundPayload:
    assignments = tuple(
        AssignmentPayload(
            drone_id=str(item["drone_id"]),
            cell=_coordinate(item["cell"]),
            reason=str(item["reason"]),
            subzone=item.get("subzone"),
        )
        for item in payload.get("assignments", [])
    )
    return BftRoundPayload(
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
    return DroneStatePayload(
        drone_id=str(payload["drone_id"]),
        position=_coordinate(payload["position"]),
        target=_coordinate(payload["target"]) if payload.get("target") is not None else None,
        status=str(payload["status"]),
        alive=bool(payload["alive"]),
        reachable=bool(payload["reachable"]),
        claimed_cell=_coordinate(payload["claimed_cell"]) if payload.get("claimed_cell") is not None else None,
        searched_cells=int(payload.get("searched_cells", 0)),
    )


def parse_envelope(envelope: MeshEnvelope) -> MeshEnvelope:
    return envelope
