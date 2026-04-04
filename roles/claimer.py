from __future__ import annotations

from collections import defaultdict

from auction.protocol import ClaimRequest, ZoneAssignment
from core.bft import BftCoordinator, BftRoundResult
from core.certainty_map import CertaintyMap, Coordinate
from core.mesh import MeshBus
from core.zone_selector import ZoneSelector
from roles.searcher import DroneState


class ClaimCoordinator:
    def __init__(self, *, mesh: MeshBus, selector: ZoneSelector, bft: BftCoordinator) -> None:
        self.mesh = mesh
        self.selector = selector
        self.bft = bft

    def build_claims(
        self,
        drones: list[DroneState],
        *,
        certainty_map: CertaintyMap,
        claimed_zones: set[Coordinate],
        now_ms: int,
    ) -> list[ClaimRequest]:
        claims: list[ClaimRequest] = []
        for drone in drones:
            if not drone.alive or not drone.reachable or drone.target_cell is not None:
                continue
            drone.status = "computing"
            selection = self.selector.select_next_zone(
                certainty_map,
                claimed_zones=claimed_zones,
                current_position=drone.position,
            )
            if selection is None:
                continue
            drone.status = "claiming"
            claim = ClaimRequest(
                claim_id=f"{drone.drone_id}:{selection.coordinate[0]}:{selection.coordinate[1]}:{now_ms}",
                drone_id=drone.drone_id,
                cell=selection.coordinate,
                position=drone.position,
                timestamp_ms=now_ms,
            )
            claims.append(claim)
            self.mesh.publish(
                "swarm/zone_claims",
                {
                    "claim_id": claim.claim_id,
                    "drone_id": claim.drone_id,
                    "cell": claim.cell,
                },
                timestamp_ms=now_ms,
            )
        return claims

    def resolve_batch(
        self,
        claims: list[ClaimRequest],
        *,
        certainty_map: CertaintyMap,
        claimed_zones: set[Coordinate],
        now_ms: int,
    ) -> tuple[dict[str, ZoneAssignment], list[BftRoundResult]]:
        assignments: dict[str, ZoneAssignment] = {}
        rounds: list[BftRoundResult] = []
        grouped: dict[Coordinate, list[ClaimRequest]] = defaultdict(list)
        for claim in claims:
            grouped[claim.cell].append(claim)

        reserved = set(claimed_zones)
        for cell in sorted(grouped):
            result = self.bft.resolve_claims(
                grouped[cell],
                certainty_map=certainty_map,
                selector=self.selector,
                claimed_zones=reserved,
            )
            rounds.append(result)
            self.mesh.publish(
                f"swarm/bft_round/{result.round_id}",
                {
                    "cell": result.cell,
                    "assignments": [
                        {
                            "drone_id": assignment.drone_id,
                            "cell": assignment.cell,
                            "reason": assignment.reason,
                            "subzone": assignment.subzone,
                        }
                        for assignment in result.assignments
                    ],
                    "rationale": result.rationale,
                },
                timestamp_ms=now_ms,
            )
            for assignment in result.assignments:
                assignments[assignment.drone_id] = assignment
                if assignment.subzone is None:
                    reserved.add(assignment.cell)
                else:
                    reserved.add(assignment.cell)
        return assignments, rounds
