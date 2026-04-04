from __future__ import annotations

from dataclasses import dataclass

from auction.protocol import AuctionDecision, ClaimRequest, ZoneAssignment, resolve_conflict
from core.certainty_map import CertaintyMap, Coordinate
from core.zone_selector import ZoneSelector


@dataclass(frozen=True, slots=True)
class VoteRecord:
    voter_id: str
    choice: str
    signature: str


@dataclass(frozen=True, slots=True)
class BftRoundResult:
    round_id: int
    cell: Coordinate
    assignments: tuple[ZoneAssignment, ...]
    votes: tuple[VoteRecord, ...]
    rationale: str


class BftCoordinator:
    def __init__(self, peer_ids: list[str]) -> None:
        self.peer_ids = tuple(peer_ids)
        self._round_id = 0

    def resolve_claims(
        self,
        claims: list[ClaimRequest],
        *,
        certainty_map: CertaintyMap,
        selector: ZoneSelector,
        claimed_zones: set[Coordinate],
    ) -> BftRoundResult:
        self._round_id += 1
        decision: AuctionDecision = resolve_conflict(
            claims,
            certainty_map=certainty_map,
            selector=selector,
            claimed_zones=claimed_zones,
        )
        lead_assignment = decision.assignments[0]
        choice = lead_assignment.drone_id if lead_assignment.subzone is None else "split"
        votes = tuple(
            VoteRecord(
                voter_id=peer_id,
                choice=choice,
                signature=f"sig:{peer_id}:{self._round_id}:{choice}",
            )
            for peer_id in self.peer_ids
        )
        return BftRoundResult(
            round_id=self._round_id,
            cell=decision.cell,
            assignments=decision.assignments,
            votes=votes,
            rationale=decision.rationale,
        )

    def confirm_release(self, *, drone_id: str, cell: Coordinate) -> BftRoundResult:
        self._round_id += 1
        choice = f"release:{drone_id}"
        votes = tuple(
            VoteRecord(
                voter_id=peer_id,
                choice=choice,
                signature=f"sig:{peer_id}:{self._round_id}:{choice}",
            )
            for peer_id in self.peer_ids
        )
        return BftRoundResult(
            round_id=self._round_id,
            cell=cell,
            assignments=(),
            votes=votes,
            rationale="stale heartbeat timeout -> release confirmed",
        )
