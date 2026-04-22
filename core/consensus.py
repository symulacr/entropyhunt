from __future__ import annotations

import threading
import time
import uuid
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from auction.protocol import AuctionDecision, ClaimRequest, ZoneAssignment, resolve_conflict

if TYPE_CHECKING:
    from core.certainty import CertaintyMap, Coordinate
    from core.mesh import MeshBusProtocol
    from core.selector import ZoneSelector


@dataclass(frozen=True, slots=True)
class VoteRecord:
    voter_id: str
    choice: str
    contest_id: str
    timestamp_ms: int
    nonce: str = field(default="")


@dataclass(frozen=True, slots=True)
class ConsensusRoundResult:
    round_id: int
    contest_id: str
    cell: Coordinate
    assignments: tuple[ZoneAssignment, ...]
    votes: tuple[VoteRecord, ...]
    rationale: str


@dataclass
class ResolveClaimsRequest:
    certainty_map: CertaintyMap
    selector: ZoneSelector
    claimed_zones: set[Coordinate]
    now_ms: int = 0
    initiator_id: str | None = None
    per_peer_maps: dict[str, CertaintyMap] | None = None


class DeterministicResolver:
    def __init__(self, peer_ids: list[str], *, mesh: MeshBusProtocol | None = None,
                 quorum_timeout_s: float = 0.5) -> None:
        self.peer_ids = tuple(dict.fromkeys(peer_ids)) if peer_ids else ()
        self.mesh = mesh
        self._quorum_timeout_s = quorum_timeout_s
        self._round_id = 0
        self.last_received_votes: tuple[VoteRecord, ...] = ()
        self._seen_votes: set[tuple[str, str]] = set()
        self._seen_votes_order: list[tuple[str, str]] = []
        self._vote_lock = threading.Lock()
        if self.mesh is not None:
            for peer_id in self.peer_ids:
                subscriber_id = self._subscriber_id(peer_id)
                self.mesh.subscribe(subscriber_id, "swarm/zone_claims")
                self.mesh.subscribe(subscriber_id, "swarm/consensus_votes/#")
                self.mesh.subscribe(subscriber_id, "swarm/consensus_result/#")

    @staticmethod
    def _subscriber_id(peer_id: str) -> str:
        return f"consensus::{peer_id}"

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
    ) -> ConsensusRoundResult:
        return ConsensusRoundResult(
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
        nonce: str = "",
    ) -> tuple[VoteRecord, ...]:
        lead_assignment = decision.assignments[0]
        choice = lead_assignment.drone_id if lead_assignment.subzone is None else "split"
        return tuple(
            VoteRecord(
                voter_id=peer_id,
                choice=choice,
                contest_id=contest_id,
                timestamp_ms=now_ms,
                nonce=nonce,
            )
            for peer_id in self.peer_ids
        )

    def _collect_peer_votes(
        self,
        *,
        contest_id: str,
        round_id: int,
        claims: list[ClaimRequest],
        certainty_map: CertaintyMap,
        selector: ZoneSelector,
        claimed_zones: set[Coordinate],
        now_ms: int,
        nonce: str = "",
        per_peer_maps: dict[str, CertaintyMap] | None = None,
    ) -> None:
        assert self.mesh is not None
        mesh = self.mesh
        local_votes: deque[dict[str, Any]] = deque()
        vote_lock = threading.Lock()

        def _vote(peer_id: str) -> None:
            subscriber_id = self._subscriber_id(peer_id)
            for envelope in mesh.poll(subscriber_id):
                if envelope.topic != "swarm/zone_claims":
                    continue
                if envelope.payload.get("contest_id") != contest_id:
                    continue
                peer_map = (per_peer_maps or {}).get(peer_id, certainty_map)
                peer_decision = resolve_conflict(
                    claims,
                    certainty_map=peer_map,
                    selector=selector,
                    claimed_zones=claimed_zones,
                )
                peer_lead = peer_decision.assignments[0]
                vote_choice = peer_lead.drone_id if peer_lead.subzone is None else "split"
                with vote_lock:
                    local_votes.append({
                        "contest_id": contest_id,
                        "round_id": round_id,
                        "drone_id": peer_id,
                        "vote": vote_choice,
                        "timestamp_ms": now_ms,
                        "nonce": nonce,
                    })

        threads = [
            threading.Thread(target=_vote, args=(pid,), daemon=True)
            for pid in self.peer_ids
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=self._quorum_timeout_s)

        with vote_lock:
            votes_snapshot = list(local_votes)
        for payload in votes_snapshot:
            mesh.publish(
                f"swarm/consensus_votes/{contest_id}",
                payload,
                timestamp_ms=now_ms,
                sender_id=payload["drone_id"],
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

    def _collect_quorum_votes(
        self,
        *,
        initiator_subscriber: str,
        contest_id: str,
        quorum: int,
    ) -> tuple[VoteRecord, ...]:
        assert self.mesh is not None
        received: dict[str, VoteRecord] = {}
        deadline = time.monotonic() + self._quorum_timeout_s
        notify = getattr(self.mesh, "_notify", None)
        while len(received) < quorum:
            envelopes = self.mesh.poll(
                initiator_subscriber,
                topic_pattern=f"swarm/consensus_votes/{contest_id}",
            )
            if not envelopes:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                if notify is not None:
                    notify.clear()
                    notify.wait(timeout=remaining)
                else:
                    time.sleep(min(remaining, 0.05))
                continue
            for envelope in envelopes:
                vote = VoteRecord(
                    voter_id=str(envelope.payload["drone_id"]),
                    choice=str(envelope.payload["vote"]),
                    contest_id=str(envelope.payload["contest_id"]),
                    timestamp_ms=int(envelope.payload["timestamp_ms"]),
                    nonce=str(envelope.payload.get("nonce", "")),
                )
                seen_key = (vote.contest_id, vote.voter_id)
                with self._vote_lock:
                    if seen_key in self._seen_votes:
                        continue
                    self._seen_votes.add(seen_key)
                    self._seen_votes_order.append(seen_key)
                    if len(self._seen_votes) > 2000:
                        evict = self._seen_votes_order.pop(0)
                        self._seen_votes.discard(evict)
                received[vote.voter_id] = vote
        return tuple(sorted(received.values(), key=lambda v: v.voter_id))

    def resolve_claims(
        self,
        claims: list[ClaimRequest],
        request: ResolveClaimsRequest,
    ) -> ConsensusRoundResult:
        certainty_map = request.certainty_map
        selector = request.selector
        claimed_zones = request.claimed_zones
        now_ms = request.now_ms
        initiator_id = request.initiator_id
        self._round_id += 1
        round_id = self._round_id
        round_nonce = uuid.uuid4().hex
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
            votes = self._fallback_votes(
                contest_id=contest_id, decision=decision, now_ms=now_ms, nonce=round_nonce,
            )
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
        self._collect_peer_votes(
            contest_id=contest_id,
            round_id=round_id,
            claims=claims,
            certainty_map=certainty_map,
            selector=selector,
            claimed_zones=claimed_zones,
            now_ms=now_ms,
            nonce=round_nonce,
            per_peer_maps=request.per_peer_maps,
        )
        quorum = len(self.peer_ids) // 2 + 1
        received_votes = self._collect_quorum_votes(
            initiator_subscriber=initiator_subscriber,
            contest_id=contest_id,
            quorum=quorum,
        )
        if len(received_votes) < quorum:
            if not received_votes:
                _msg = (
                    f"contention {contest_id} failed quorum collection over the mesh bus: "
                    f"received {len(received_votes)} / {quorum} votes"
                )
                raise RuntimeError(_msg)
            fallback_votes = self._fallback_votes(
                contest_id=contest_id,
                decision=decision,
                now_ms=now_ms,
                nonce=round_nonce,
            )
            self.last_received_votes = fallback_votes
            return self._apply_round(
                round_id=round_id,
                contest_id=contest_id,
                decision=decision,
                votes=fallback_votes,
            )
        winning_choice = self._majority_choice(received_votes, fallback=fallback_choice)
        result_decision = decision
        if winning_choice not in (fallback_choice, "split"):
            winning_assignment = next(
                (a for a in decision.assignments if a.drone_id == winning_choice), None,
            )
            if winning_assignment is not None:
                result_decision = AuctionDecision(
                    cell=decision.cell,
                    assignments=(
                        winning_assignment,
                        *[a for a in decision.assignments if a.drone_id != winning_choice],
                    ),
                    rationale=f"majority vote -> {winning_choice}",
                )
        self.mesh.publish(
            f"swarm/consensus_result/{contest_id}",
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

    @property
    def round_id(self) -> int:
        return self._round_id

    def sync_round_id(self, round_id: int) -> None:
        self._round_id = max(self._round_id, round_id)

    def set_peer_ids(self, peer_ids: list[str]) -> None:
        self.peer_ids = tuple(dict.fromkeys(peer_ids)) if peer_ids else ()

    def confirm_release(
        self,
        *,
        drone_id: str,
        cell: Coordinate,
        now_ms: int | None = None,
    ) -> ConsensusRoundResult:
        self._round_id += 1
        if now_ms is None:
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
        return ConsensusRoundResult(
            round_id=self._round_id,
            contest_id=contest_id,
            cell=cell,
            assignments=(),
            votes=votes,
            rationale="stale heartbeat timeout -> release confirmed",
        )
