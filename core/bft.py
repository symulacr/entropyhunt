from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from auction.protocol import AuctionDecision, ClaimRequest, ZoneAssignment, resolve_conflict
from core.certainty_map import CertaintyMap, Coordinate
from core.mesh import InMemoryMeshBus
from core.zone_selector import ZoneSelector


@dataclass(frozen=True, slots=True)
class VoteRecord:
    voter_id: str
    choice: str
    contest_id: str
    timestamp_ms: int


@dataclass(frozen=True, slots=True)
class BftRoundResult:
    round_id: int
    contest_id: str
    cell: Coordinate
    assignments: tuple[ZoneAssignment, ...]
    votes: tuple[VoteRecord, ...]
    rationale: str


class BftCoordinator:
    def __init__(self, peer_ids: list[str], *, mesh: InMemoryMeshBus | None = None) -> None:
        self.peer_ids = tuple(peer_ids)
        self.mesh = mesh
        self._round_id = 0
        self.last_received_votes: tuple[VoteRecord, ...] = tuple()
        if self.mesh is not None:
            for peer_id in self.peer_ids:
                subscriber_id = self._subscriber_id(peer_id)
                self.mesh.subscribe(subscriber_id, "swarm/zone_claims")
                self.mesh.subscribe(subscriber_id, "swarm/bft_votes/#")
                self.mesh.subscribe(subscriber_id, "swarm/bft_result/#")

    @staticmethod
    def _subscriber_id(peer_id: str) -> str:
        return f"bft::{peer_id}"

    @staticmethod
    def _contest_id(round_id: int, cell: Coordinate, *, now_ms: int) -> str:
        return f"{round_id}:{cell[0]}:{cell[1]}:{now_ms}"

    def _apply_round(
        self,
        *,
        round_id: int,
        contest_id: str,
        decision: AuctionDecision,
        votes: tuple[VoteRecord, ...],
    ) -> BftRoundResult:
        return BftRoundResult(
            round_id=round_id,
            contest_id=contest_id,
            cell=decision.cell,
            assignments=decision.assignments,
            votes=votes,
            rationale=decision.rationale,
        )

    def _fallback_votes(
        self,
        *,
        contest_id: str,
        decision: AuctionDecision,
        now_ms: int,
    ) -> tuple[VoteRecord, ...]:
        lead_assignment = decision.assignments[0]
        choice = lead_assignment.drone_id if lead_assignment.subzone is None else "split"
        return tuple(
            VoteRecord(
                voter_id=peer_id,
                choice=choice,
                contest_id=contest_id,
                timestamp_ms=now_ms,
            )
            for peer_id in self.peer_ids
        )

    @staticmethod
    def _majority_choice(
        votes: tuple[VoteRecord, ...],
        *,
        fallback: str,
    ) -> str:
        counts = Counter(vote.choice for vote in votes)
        if not counts:
            return fallback
        [(choice, total), *rest] = counts.most_common()
        if rest and total == rest[0][1]:
            return fallback
        return choice

    def resolve_claims(
        self,
        claims: list[ClaimRequest],
        *,
        certainty_map: CertaintyMap,
        selector: ZoneSelector,
        claimed_zones: set[Coordinate],
        now_ms: int = 0,
        initiator_id: str | None = None,
    ) -> BftRoundResult:
        self._round_id += 1
        round_id = self._round_id
        decision: AuctionDecision = resolve_conflict(
            claims,
            certainty_map=certainty_map,
            selector=selector,
            claimed_zones=claimed_zones,
        )
        contest_id = self._contest_id(round_id, decision.cell, now_ms=now_ms)
        initiator = initiator_id or self.peer_ids[0]
        initiator_subscriber = self._subscriber_id(initiator)
        if self.mesh is None or len(claims) == 1:
            votes = self._fallback_votes(contest_id=contest_id, decision=decision, now_ms=now_ms)
            self.last_received_votes = votes
            return self._apply_round(
                round_id=round_id,
                contest_id=contest_id,
                decision=decision,
                votes=votes,
            )

        contest_payload: dict[str, Any] = {
            "kind": "CLAIM_CONTEST",
            "contest_id": contest_id,
            "round_id": round_id,
            "claims": [
                {
                    "claim_id": claim.claim_id,
                    "drone_id": claim.drone_id,
                    "cell": list(claim.cell),
                    "position": list(claim.position),
                    "timestamp_ms": claim.timestamp_ms,
                }
                for claim in claims
            ],
        }
        self.mesh.publish(
            "swarm/zone_claims",
            contest_payload,
            timestamp_ms=now_ms,
            sender_id=initiator,
        )
        lead_assignment = decision.assignments[0]
        fallback_choice = lead_assignment.drone_id if lead_assignment.subzone is None else "split"
        for peer_id in self.peer_ids:
            subscriber_id = self._subscriber_id(peer_id)
            for envelope in self.mesh.poll(subscriber_id):
                if envelope.topic != "swarm/zone_claims":
                    continue
                if envelope.payload.get("contest_id") != contest_id:
                    continue
                peer_decision = resolve_conflict(
                    claims,
                    certainty_map=certainty_map,
                    selector=selector,
                    claimed_zones=claimed_zones,
                )
                peer_lead = peer_decision.assignments[0]
                vote_choice = peer_lead.drone_id if peer_lead.subzone is None else "split"
                self.mesh.publish(
                    f"swarm/bft_votes/{contest_id}",
                    {
                        "contest_id": contest_id,
                        "round_id": round_id,
                        "drone_id": peer_id,
                        "vote": vote_choice,
                        "timestamp_ms": now_ms,
                    },
                    timestamp_ms=now_ms,
                    sender_id=peer_id,
                )
        quorum = len(self.peer_ids) // 2 + 1
        received: dict[str, VoteRecord] = {}
        deadline_ms = now_ms + 500
        while len(received) < quorum and now_ms <= deadline_ms:
            envelopes = self.mesh.poll(initiator_subscriber, topic_pattern=f"swarm/bft_votes/{contest_id}")
            if not envelopes:
                break
            for envelope in envelopes:
                vote = VoteRecord(
                    voter_id=str(envelope.payload["drone_id"]),
                    choice=str(envelope.payload["vote"]),
                    contest_id=str(envelope.payload["contest_id"]),
                    timestamp_ms=int(envelope.payload["timestamp_ms"]),
                )
                received[vote.voter_id] = vote
        received_votes = tuple(sorted(received.values(), key=lambda vote: vote.voter_id))
        if len(received_votes) < quorum:
            raise RuntimeError(
                f"contention {contest_id} failed quorum collection over the mesh bus: "
                f"received {len(received_votes)} / {quorum} votes"
            )
        winning_choice = self._majority_choice(received_votes, fallback=fallback_choice)
        result_decision = decision
        if winning_choice != fallback_choice:
            result_decision = resolve_conflict(
                claims,
                certainty_map=certainty_map,
                selector=selector,
                claimed_zones=claimed_zones,
            )
        self.mesh.publish(
            f"swarm/bft_result/{contest_id}",
            {
                "contest_id": contest_id,
                "round_id": round_id,
                "cell": list(result_decision.cell),
                "assignments": [
                    {
                        "drone_id": assignment.drone_id,
                        "cell": list(assignment.cell),
                        "reason": assignment.reason,
                        "subzone": assignment.subzone,
                    }
                    for assignment in result_decision.assignments
                ],
                "rationale": result_decision.rationale,
                "vote_count": len(received_votes),
            },
            timestamp_ms=now_ms,
            sender_id=initiator,
        )
        self.last_received_votes = received_votes
        return self._apply_round(
            round_id=round_id,
            contest_id=contest_id,
            decision=result_decision,
            votes=received_votes,
        )

    def confirm_release(self, *, drone_id: str, cell: Coordinate) -> BftRoundResult:
        self._round_id += 1
        now_ms = self._round_id * 1000
        choice = f"release:{drone_id}"
        contest_id = self._contest_id(self._round_id, cell, now_ms=now_ms)
        votes = tuple(
            VoteRecord(
                voter_id=peer_id,
                choice=choice,
                contest_id=contest_id,
                timestamp_ms=now_ms,
            )
            for peer_id in self.peer_ids
        )
        return BftRoundResult(
            round_id=self._round_id,
            contest_id=contest_id,
            cell=cell,
            assignments=(),
            votes=votes,
            rationale="stale heartbeat timeout -> release confirmed",
        )
