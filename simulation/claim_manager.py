
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from auction.protocol import ClaimRequest
from core.consensus import ResolveClaimsRequest
from simulation.protocol import (
    ClaimPayload,
    ConsensusRoundPayload,
    consensus_round_topic,
    make_assignment_payload,
    make_claim_payload,
    make_consensus_round_payload,
    parse_claim_payload,
    parse_consensus_round_payload,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.certainty import CertaintyMap, Coordinate
    from core.consensus import ConsensusRoundResult, DeterministicResolver
    from core.mesh import MeshBusProtocol, MeshEnvelope
    from core.selector import ZoneSelector
    from simulation.mesh_handler import PeerMeshHandler
    from simulation.peer_config import PeerRuntimeConfig
    from simulation.proof import PeerProofLogger

_MAX_TRACKED_SET_SIZE = 500

class PeerClaimManager:

    def __init__(
        self,
        *,
        config: PeerRuntimeConfig,
        mesh: MeshBusProtocol,
        resolver: DeterministicResolver,
        selector: ZoneSelector,
        mesh_handler: PeerMeshHandler,
        proof_logger: PeerProofLogger,
    ) -> None:
        self.config = config
        self.mesh = mesh
        self._resolver = resolver
        self.selector = selector
        self.mesh_handler = mesh_handler
        self.proof_logger = proof_logger

        self.auctions: int = 0
        self._pending_claims: dict[str, ClaimRequest] = {}
        self._resolved_claim_ids: set[str] = set()
        self._processed_rounds: set[int] = set()
        self._released_stale: set[str] = set()
        self._pending_claims_by_cell: dict[Coordinate, list[str]] = {}
        self._pending_claim_timestamps: dict[str, int] = {}

    def handle_claim(self, envelope: MeshEnvelope) -> None:
        payload = parse_claim_payload(envelope.payload)
        if payload.claim_id in self._resolved_claim_ids:
            return
        claim = ClaimRequest(
            claim_id=payload.claim_id,
            drone_id=payload.drone_id,
            cell=payload.cell,
            position=payload.position,
            timestamp_ms=payload.timestamp_ms,
        )
        self._pending_claims[payload.claim_id] = claim
        self._pending_claims_by_cell.setdefault(claim.cell, []).append(claim.claim_id)
        self._pending_claim_timestamps[payload.claim_id] = payload.timestamp_ms
        self.mesh_handler.ensure_peer(
            payload.drone_id,
            position=payload.position,
        ).status = "claiming"

    def apply_round(
        self,
        round_payload: ConsensusRoundPayload,
        now_ms: int,
        log_fn: Callable[..., None] | None = None,
    ) -> None:
        if round_payload.round_id in self._processed_rounds:
            return
        self._processed_rounds.add(round_payload.round_id)
        self._resolver.sync_round_id(round_payload.round_id)
        self.proof_logger.append_proof(now_ms // 1000, round_payload)
        if round_payload.released_by is not None:
            stale_peer = self.mesh_handler.ensure_peer(round_payload.released_by)
            stale_peer.mark_stale()
            self.mesh_handler.mark_stale_since(round_payload.released_by, now_ms)
        if len(round_payload.assignments) > 1:
            self.auctions += 1
        self._evict_pending_claims_for_cell(round_payload.cell)
        for assignment in round_payload.assignments:
            drone = self.mesh_handler.ensure_peer(assignment.drone_id)
            if assignment.reason == "idle":
                drone.clear_assignment()
            else:
                drone.set_assignment(assignment.cell, subzone=assignment.subzone)
                drone.status = (
                    "claim_won" if assignment.drone_id == self.config.peer_id else drone.status
                )
        if log_fn is not None:
            log_fn("consensus", f"round {round_payload.round_id} resolved {round_payload.cell}")

    def handle_consensus_round(
        self,
        envelope: MeshEnvelope,
        now_ms: int,
        log_fn: Callable[..., None] | None = None,
    ) -> None:
        self.apply_round(parse_consensus_round_payload(envelope.payload), now_ms, log_fn=log_fn)

    def detect_stale_peers(self, now_ms: int, tick_ms: int, log_fn: Callable[..., None]) -> None:
        timeout_ms = max(
            self.config.stale_after_seconds * 1000,
            tick_ms * self.config.stale_timeout_tick_multiplier,
        )
        status = self.mesh_handler.heartbeat.detect_stale(
            now_ms=now_ms,
            timeout_ms=timeout_ms,
        )
        for drone_id in status.stale:
            if drone_id == self.config.peer_id:
                continue
            peer = self.mesh_handler.ensure_peer(drone_id)
            if not peer.alive:
                continue
            if (
                drone_id not in self._released_stale
                and peer.claimed_cell is not None
            ):
                release_round = self._resolver.confirm_release(
                    drone_id=drone_id,
                    cell=peer.claimed_cell,
                    now_ms=now_ms,
                )
                payload = make_consensus_round_payload(
                    round_id=release_round.round_id,
                    contest_id=release_round.contest_id,
                    cell=release_round.cell,
                    assignments=[],
                    rationale=release_round.rationale,
                    released_by=drone_id,
                )
                self.mesh.publish(
                    consensus_round_topic(release_round.round_id),
                    payload,
                    timestamp_ms=now_ms,
                    sender_id=self.config.peer_id,
                )
                self.apply_round(parse_consensus_round_payload(payload), now_ms, log_fn=log_fn)
                self._released_stale.add(drone_id)
            peer.mark_stale()
            self.mesh_handler.mark_stale_since(drone_id, now_ms)

    def claim_resolution_delay_ms(self, tick_ms: int) -> int:
        return tick_ms * (2 if self.config.transport == "foxmq" else 1)

    def resolve_pending_claims(
        self,
        now_ms: int,
        tick_ms: int,
        certainty_map: CertaintyMap,
        log_fn: Callable[..., None],
    ) -> None:
        ttl_ms = 2 * self.claim_resolution_delay_ms(tick_ms)
        expired = [
            claim_id
            for claim_id, ts in self._pending_claim_timestamps.items()
            if now_ms - ts > ttl_ms
        ]
        for claim_id in expired:
            self._pending_claims.pop(claim_id, None)
            self._pending_claim_timestamps.pop(claim_id, None)
            for cell_claim_ids in self._pending_claims_by_cell.values():
                if claim_id in cell_claim_ids:
                    cell_claim_ids.remove(claim_id)
        mature_claims = [
            claim
            for claim in self._pending_claims.values()
            if claim.timestamp_ms <= now_ms - self.claim_resolution_delay_ms(tick_ms)
            and claim.claim_id not in self._resolved_claim_ids
        ]
        grouped: dict[Coordinate, list[ClaimRequest]] = {}
        for claim in mature_claims:
            grouped.setdefault(claim.cell, []).append(claim)
        for cell in sorted(grouped):
            result: ConsensusRoundResult = self._resolver.resolve_claims(
                grouped[cell],
                ResolveClaimsRequest(
                    certainty_map=certainty_map,
                    selector=self.selector,
                    claimed_zones=self.mesh_handler.claimed_zones(),
                ),
            )
            assignments = [
                make_assignment_payload(
                    drone_id=assignment.drone_id,
                    cell=assignment.cell,
                    reason=assignment.reason,
                    subzone=assignment.subzone,
                )
                for assignment in result.assignments
            ]
            payload = make_consensus_round_payload(
                round_id=result.round_id,
                contest_id=result.contest_id,
                cell=result.cell,
                assignments=assignments,
                rationale=result.rationale,
            )
            self.mesh.publish(
                consensus_round_topic(result.round_id),
                payload,
                timestamp_ms=now_ms,
                sender_id=self.config.peer_id,
            )
            self.apply_round(parse_consensus_round_payload(payload), now_ms, log_fn=log_fn)
            self._resolved_claim_ids.update(claim.claim_id for claim in grouped[cell])
        for claim_id in list(self._pending_claims):
            if claim_id in self._resolved_claim_ids:
                del self._pending_claims[claim_id]
                self._pending_claim_timestamps.pop(claim_id, None)
                for cell_claim_ids in self._pending_claims_by_cell.values():
                    if claim_id in cell_claim_ids:
                        cell_claim_ids.remove(claim_id)
        if len(self._processed_rounds) > _MAX_TRACKED_SET_SIZE:
            oldest_rounds = sorted(self._processed_rounds)[
                : len(self._processed_rounds) - _MAX_TRACKED_SET_SIZE
            ]
            self._processed_rounds -= set(oldest_rounds)
        if len(self._resolved_claim_ids) > _MAX_TRACKED_SET_SIZE:
            oldest_claims = sorted(self._resolved_claim_ids)[
                : len(self._resolved_claim_ids) - _MAX_TRACKED_SET_SIZE
            ]
            self._resolved_claim_ids -= set(oldest_claims)

    def build_and_publish_claim(
        self,
        cell: Coordinate,
        now_ms: int,
        position: Coordinate,
        log_fn: Callable[..., None],
    ) -> ClaimRequest:
        claim = ClaimRequest(
            claim_id=f"{self.config.peer_id}:{cell[0]}:{cell[1]}:{now_ms}",
            drone_id=self.config.peer_id,
            cell=cell,
            position=position,
            timestamp_ms=now_ms,
        )
        self._pending_claims[claim.claim_id] = claim
        self._pending_claim_timestamps[claim.claim_id] = now_ms
        self._pending_claims_by_cell.setdefault(cell, []).append(claim.claim_id)
        self.mesh.publish(
            "swarm/zone_claims",
            make_claim_payload(
                ClaimPayload(
                    claim_id=claim.claim_id,
                    drone_id=claim.drone_id,
                    cell=claim.cell,
                    position=claim.position,
                    timestamp_ms=claim.timestamp_ms,
                ),
            ),
            timestamp_ms=now_ms,
            sender_id=self.config.peer_id,
        )
        log_fn("claim", f"{self.config.peer_id} targeting {cell}", claim_id=claim.claim_id)
        return claim

    def has_pending_claims(self) -> bool:
        return bool(self._pending_claims)

    def pending_claim_ids(self) -> set[str]:
        return set(self._pending_claims.keys())

    @property
    def has_processed_rounds(self) -> bool:
        return bool(self._processed_rounds)

    @property
    def resolver(self) -> DeterministicResolver:
        return self._resolver

    @property
    def round_id(self) -> int:
        return self._resolver.round_id

    def any_drone_claiming(self) -> bool:
        return any(drone.status == "claiming" for drone in self.mesh_handler.peer_drones.values())

    def _evict_pending_claims_for_cell(self, cell: Coordinate) -> None:
        claim_ids = self._pending_claims_by_cell.pop(cell, [])
        for claim_id in claim_ids:
            self._pending_claims.pop(claim_id, None)
            self._pending_claim_timestamps.pop(claim_id, None)
