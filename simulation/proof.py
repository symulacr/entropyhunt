
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from simulation.protocol import ConsensusRoundPayload

class ProofLogger:

    _FLUSH_INTERVAL = 10

    def __init__(
        self,
        proofs_path: str | Path,
        *,
        source_mode: str = "stub",
        flush_interval: int | None = None,
        truncate: bool = True,
    ) -> None:
        self.proofs_path = Path(proofs_path)
        self._source_mode = source_mode
        self.events: list[dict[str, Any]] = []
        self._proof_ids: set[str] = set()
        self._buffer: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        if flush_interval is not None:
            self._FLUSH_INTERVAL = flush_interval
        if truncate:
            self.proofs_path.parent.mkdir(parents=True, exist_ok=True)
            self.proofs_path.write_text("")

    def log(
        self,
        time_seconds: int,
        event_type: str,
        message: str,
        **data: object,
    ) -> None:
        source_mode = data.pop("source_mode", None) or self._source_mode
        payload = {
            "t": time_seconds,
            "type": event_type,
            "message": message,
            "source": "runtime",
            "source_mode": source_mode,
            "synthetic": False,
            **data,
        }
        self.events.append(payload)
        self._write_line(payload)

    def append_proof(self, time_seconds: int, round_payload: ConsensusRoundPayload) -> None:
        contest_id = round_payload.contest_id or f"round-{round_payload.round_id}"
        if contest_id in self._proof_ids:
            return
        self._proof_ids.add(contest_id)
        payload = {
            "t": time_seconds,
            "type": "consensus_result",
            "contest_id": contest_id,
            "round_id": round_payload.round_id,
            "cell": list(round_payload.cell),
            "assignments": [asdict(assignment) for assignment in round_payload.assignments],
            "released_by": round_payload.released_by,
            "source": "runtime",
            "source_mode": "peer",
            "synthetic": False,
        }
        self._write_line(payload)

    def _write_line(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._buffer.append(payload)
            if len(self._buffer) >= self._FLUSH_INTERVAL:
                self._flush_locked()

    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        if not self._buffer:
            return
        self.proofs_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(payload) + "\n" for payload in self._buffer]
        self._buffer.clear()
        with self.proofs_path.open("a", encoding="utf-8") as handle:
            handle.writelines(lines)

    def close(self) -> None:
        self.flush()

    def finalize(self, output_path: str | Path, *, mesh_transport: str = "in-process") -> None:
        self.flush()
        events = self._read_events()
        audit_trail = self._build_audit_trail(events)
        consensus_rounds = [
            e for e in events
            if e.get("type") in ("consensus_result", "bft_result", "consensus", "auction")
        ]
        poc: dict[str, Any] = {
            "version": "1.1",
            "generated_at": datetime.now(UTC).isoformat(),
            "swarm_id": hashlib.sha256(
                json.dumps(sorted(json.dumps(e, sort_keys=True) for e in audit_trail)).encode(),
            ).hexdigest()[:32],
            "mission": "search_and_rescue",
            "track": "Track 2 - Search & Rescue Swarms",
            "mesh_transport": mesh_transport,
            "bft_rounds_total": len([
                r for r in consensus_rounds
                if r.get("rationale") != "single-claim quorum"
            ]),
            "nodes_that_dropped": sorted({
                str(e.get("peer_id", e.get("drone_id", "")))
                for e in events
                if e.get("type") in (
                    "peer_dropped", "node_failure", "stale", "heartbeat_timeout", "failure",
                ) and (e.get("peer_id") or e.get("drone_id"))
            }),
            "recovery_events": [
                {"t": e.get("t"), "peer_id": str(e.get("peer_id", e.get("drone_id", "")))}
                for e in events
                if e.get("type") in ("peer_recovered", "node_recovery", "reconnect", "recovery")
            ],
            "packet_loss_survived": any(e.get("type") == "packet_dropped" for e in events),
            "survivor_found": any(e.get("type") in ("survivor", "survivor_found") for e in events),
            "total_events": len(events),
            "active_voters": len(self._active_voter_ids(consensus_rounds)),
            "consensus_rounds": consensus_rounds,
            "peer_audit_hashes": compute_peer_signatures(audit_trail),
            "audit_trail": audit_trail,
        }
        coverage = next(
            (e.get("coverage_pct") for e in reversed(events) if e.get("type") == "grid_coverage"),
            None,
        )
        if coverage is not None:
            poc["grid_coverage_pct"] = coverage
        if mesh_transport == "foxmq":
            ids = {
                str(e.get("peer_id", e.get("drone_id", "")))
                for e in events
                if e.get("peer_id") or e.get("drone_id")
            }
            ids.discard("")
            poc["foxmq_nodes"] = len(ids) or 1
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(poc, indent=2))

    def _read_events(self) -> list[dict[str, Any]]:
        if not self.proofs_path.exists():
            return []
        events = []
        for raw_line in self.proofs_path.read_text().splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events

    @staticmethod
    def _build_audit_trail(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        trail = []
        for e in events:
            entry: dict[str, Any] = {
                "t": e.get("t"), "type": e.get("type"), "message": e.get("message", ""),
            }
            if "peer_id" in e:
                entry["peer_id"] = e["peer_id"]
            if "drone_id" in e:
                entry["drone_id"] = e["drone_id"]
            claim_id = e.get("claim_id", "")
            if claim_id and ":" in str(claim_id):
                entry["claim_id"] = claim_id
            trail.append(entry)
        return trail

    @staticmethod
    def _active_voter_ids(consensus_rounds: list[dict[str, Any]]) -> set[str]:
        ids: set[str] = set()
        for r in consensus_rounds:
            for vote in r.get("votes", []):
                if isinstance(vote, dict):
                    vid = vote.get("voter_id") or vote.get("peer_id") or vote.get("drone_id")
                    if vid:
                        ids.add(str(vid))
            for a in r.get("assignments", []):
                if isinstance(a, dict) and a.get("drone_id"):
                    ids.add(str(a["drone_id"]))
        return ids

def compute_peer_signatures(audit_trail: list[dict[str, Any]]) -> dict[str, str]:
    peer_events: dict[str, list[str]] = {}
    for entry in audit_trail:
        pids: set[str] = set()
        if "peer_id" in entry:
            pids.add(str(entry["peer_id"]))
        if "drone_id" in entry:
            pids.add(str(entry["drone_id"]))
        claim_id = entry.get("claim_id", "")
        if claim_id and ":" in str(claim_id):
            pids.add(str(claim_id).split(":")[0])
        serialized = json.dumps(entry, sort_keys=True)
        for pid in pids:
            peer_events.setdefault(pid, []).append(serialized)
    peer_events.pop("local", None)
    return {
        pid: hashlib.sha256(json.dumps(sorted(evts), sort_keys=True).encode()).hexdigest()
        for pid, evts in sorted(peer_events.items())
    }

class PeerProofLogger(ProofLogger):

    def __init__(self, proofs_path: str | Path) -> None:
        super().__init__(proofs_path, source_mode="peer", truncate=False)
