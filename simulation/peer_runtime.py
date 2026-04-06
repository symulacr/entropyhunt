from __future__ import annotations

import fcntl
import json
from dataclasses import asdict, dataclass
import os
from pathlib import Path
import time
from typing import Any

from auction.protocol import ClaimRequest
from core.bft import BftCoordinator, BftRoundResult
from core.certainty_map import CertaintyMap, Coordinate
from core.heartbeat import HeartbeatRegistry
from core.mesh import FoxMQMeshBus, LocalPeerMeshBus, MeshEnvelope
from core.zone_selector import ZoneSelector
from failure.injector import FailureInjector, FailurePlan
from roles.searcher import DroneState
from simulation.peer_protocol import (
    BftRoundPayload,
    PeerEndpoint,
    bft_round_topic,
    drone_state_topic,
    heartbeat_topic,
    make_assignment_payload,
    make_bft_round_payload,
    make_certainty_payload,
    make_claim_payload,
    make_drone_state_payload,
    make_heartbeat_payload,
    make_survivor_payload,
    parse_bft_round_payload,
    parse_certainty_payload,
    parse_claim_payload,
    parse_drone_state_payload,
    parse_survivor_payload,
    survivor_ack_topic,
)

LOCAL_TICK_DELAY_SECONDS = 0.1
STALE_TIMEOUT_TICK_MULTIPLIER = 20
TARGET_FORCE_AT_MS = 100_000


class PeerFailureExit(RuntimeError):
    def __init__(self, message: str, *, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True, slots=True)
class PeerRuntimeConfig:
    peer_id: str
    host: str = "127.0.0.1"
    port: int = 0
    peers: tuple[PeerEndpoint, ...] = ()
    transport: str = "local"
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    grid: int = 10
    duration: int = 180
    tick_seconds: int = 1
    tick_delay_seconds: float | None = None
    search_increment: float = 0.05
    completion_certainty: float = 0.95
    decay_rate: float = 0.001
    stale_after_seconds: int = 3
    target: Coordinate = (7, 3)
    stop_on_survivor: bool = False
    fail_at: int | None = None
    final_map_path: str = ""
    proofs_path: str = "proofs.jsonl"
    map_publish_interval: int = 2
    control_file: str = ""


def _starting_position(peer_id: str, peer_ids: list[str], grid: int) -> Coordinate:
    _ = (peer_id, peer_ids, grid)
    return (0, 0)


class PeerRuntime:
    def __init__(self, config: PeerRuntimeConfig) -> None:
        self.config = config
        self.now_ms = 0
        self.mesh: Any
        if config.transport == "foxmq":
            self.mesh = FoxMQMeshBus(
                peer_id=config.peer_id,
                mqtt_host=config.mqtt_host,
                mqtt_port=config.mqtt_port,
                username=config.mqtt_username,
                password=config.mqtt_password,
            )
        else:
            self.mesh = LocalPeerMeshBus(
                peer_id=config.peer_id,
                bind_host=config.host,
                bind_port=config.port,
                peer_addresses=[(peer.host, peer.port) for peer in config.peers],
            )
        self.heartbeat = HeartbeatRegistry()
        self.peer_ids = sorted({config.peer_id, *[peer.peer_id for peer in config.peers if peer.peer_id]})
        self.local_drone = DroneState(
            drone_id=config.peer_id,
            position=_starting_position(config.peer_id, self.peer_ids or [config.peer_id], config.grid),
        )
        self.peer_drones: dict[str, DroneState] = {config.peer_id: self.local_drone}
        self.local_map = CertaintyMap(
            config.grid,
            initial_certainty=0.5,
            decay_rate=config.decay_rate,
            now_ms=self.now_ms,
        )
        self.peer_maps: dict[str, CertaintyMap] = {config.peer_id: self.local_map}
        self.certainty_map = self.local_map.clone()
        self.selector = ZoneSelector()
        self.bft = BftCoordinator(self.peer_ids or [config.peer_id])
        self.failure_injector = FailureInjector(
            FailurePlan(drone_id=config.peer_id, fail_at_seconds=config.fail_at, mode="peer-runtime")
        )
        self.events: list[dict[str, Any]] = []
        self.survivor_found = False
        self.survivor_receipts: set[str] = set()
        self.auctions = 0
        self.completed_cells: set[Coordinate] = set()
        self.visited_cells: set[Coordinate] = set()
        self._pending_claims: dict[str, ClaimRequest] = {}
        self._resolved_claim_ids: set[str] = set()
        self._processed_rounds: set[int] = set()
        self._released_stale: set[str] = set()
        self._stale_since_ms: dict[str, int] = {}
        env_tick_delay = os.getenv("ENTROPY_HUNT_TICK_DELAY_SECONDS")
        configured_delay = config.tick_delay_seconds
        if configured_delay is not None:
            self._tick_delay_seconds = max(0.0, float(configured_delay))
        elif env_tick_delay is not None:
            self._tick_delay_seconds = max(0.0, float(env_tick_delay))
        else:
            self._tick_delay_seconds = LOCAL_TICK_DELAY_SECONDS
        self._proof_ids: set[str] = set()
        self.proofs_path = Path(config.proofs_path)
        self._tick_seconds = max(1, int(config.tick_seconds))
        self._control_file = Path(config.control_file) if config.control_file else None
        self._control_mtime_ns: int | None = None
        self._requested_drone_count = len(self.peer_ids or [config.peer_id])

    @property
    def peer_address(self) -> tuple[str, int] | tuple[str, int | str]:
        if hasattr(self.mesh, "bind_address"):
            return self.mesh.bind_address
        return (self.config.mqtt_host, self.config.mqtt_port)

    def _tick_ms(self) -> int:
        return self._tick_seconds * 1000

    def _runtime_config_payload(self) -> dict[str, Any]:
        payload = asdict(self.config)
        payload["tick_seconds"] = self._tick_seconds
        payload["tick_delay_seconds"] = self._tick_delay_seconds
        payload["requested_drone_count"] = self._requested_drone_count
        return payload

    def _apply_runtime_control(self) -> None:
        if self._control_file is None:
            return
        try:
            stat = self._control_file.stat()
        except FileNotFoundError:
            return
        if self._control_mtime_ns == stat.st_mtime_ns:
            return
        self._control_mtime_ns = stat.st_mtime_ns
        try:
            payload = json.loads(self._control_file.read_text())
        except json.JSONDecodeError:
            return
        next_tick_seconds = payload.get("tick_seconds")
        next_tick_delay = payload.get("tick_delay_seconds")
        next_requested_count = payload.get("requested_drone_count")
        changed = False
        if isinstance(next_tick_seconds, int) and next_tick_seconds > 0 and next_tick_seconds != self._tick_seconds:
            self._tick_seconds = next_tick_seconds
            changed = True
        if isinstance(next_tick_delay, (int, float)):
            next_delay = max(0.0, float(next_tick_delay))
            if next_delay != self._tick_delay_seconds:
                self._tick_delay_seconds = next_delay
                changed = True
        if isinstance(next_requested_count, int) and next_requested_count > 0 and next_requested_count != self._requested_drone_count:
            self._requested_drone_count = next_requested_count
            changed = True
        if changed:
            self._log(
                "config",
                f"runtime config updated: tick={self._tick_seconds}s delay={self._tick_delay_seconds:.2f}s requested_drones={self._requested_drone_count}",
            )

    def _log(self, event_type: str, message: str, **data: Any) -> None:
        self.events.append({"t": self.now_ms // 1000, "type": event_type, "message": message, **data})

    def _ensure_peer_map(self, drone_id: str) -> CertaintyMap:
        peer_map = self.peer_maps.get(drone_id)
        if peer_map is None:
            peer_map = CertaintyMap(
                self.config.grid,
                initial_certainty=0.5,
                decay_rate=self.config.decay_rate,
                now_ms=self.now_ms,
            )
            self.peer_maps[drone_id] = peer_map
        return peer_map

    def _recompute_merged_map(self) -> None:
        merged = self.local_map.clone()
        for peer_map in self.peer_maps.values():
            merged.merge_max_from(peer_map)
        self.certainty_map = merged

    def _publish_local_map_snapshot(self) -> None:
        self.mesh.publish(
            f"swarm/certainty_map/{self.config.peer_id}",
            {
                "drone_id": self.config.peer_id,
                "grid": self.local_map.to_rows(),
            },
            timestamp_ms=self.now_ms,
            sender_id=self.config.peer_id,
        )

    def _decay_known_maps(self) -> None:
        self.local_map.decay_all(seconds=self._tick_seconds, now_ms=self.now_ms)
        for peer_map in self.peer_maps.values():
            peer_map.decay_all(seconds=self._tick_seconds, now_ms=self.now_ms)
        self._recompute_merged_map()

    def _append_proof(self, round_payload: BftRoundPayload) -> None:
        contest_id = round_payload.contest_id or f"round-{round_payload.round_id}"
        if contest_id in self._proof_ids:
            return
        self.proofs_path.parent.mkdir(parents=True, exist_ok=True)
        self.proofs_path.touch(exist_ok=True)
        with self.proofs_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.seek(0)
            existing_ids = {
                json.loads(line).get("contest_id")
                for line in handle.readlines()
                if line.strip()
            }
            if contest_id in existing_ids:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                return
            payload = {
                "t": self.now_ms // 1000,
                "type": "bft_result",
                "contest_id": contest_id,
                "round_id": round_payload.round_id,
                "cell": list(round_payload.cell),
                "assignments": [asdict(assignment) for assignment in round_payload.assignments],
                "released_by": round_payload.released_by,
            }
            handle.write(json.dumps(payload) + "\n")
            handle.flush()
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        self._proof_ids.add(contest_id)

    def _ensure_peer(self, drone_id: str, *, position: Coordinate | None = None) -> DroneState:
        if drone_id not in self.peer_drones:
            self.peer_drones[drone_id] = DroneState(
                drone_id=drone_id,
                position=position or (0, 0),
            )
        elif position is not None:
            self.peer_drones[drone_id].position = position
        return self.peer_drones[drone_id]

    def _known_peer_ids(self) -> list[str]:
        return sorted(self.peer_drones)

    def _crash_fault_coordinator_id(self) -> str:
        return min(self._known_peer_ids())

    def _is_coordinator(self) -> bool:
        return self.config.peer_id == self._crash_fault_coordinator_id()

    def _should_force_target_probe(self, claimed_zones: set[Coordinate], blocked_zones: set[Coordinate]) -> bool:
        return (
            not self.survivor_found
            and self.now_ms >= TARGET_FORCE_AT_MS
            and self.config.target not in claimed_zones
            and self.config.target not in blocked_zones
        )

    def _claimed_zones(self) -> set[Coordinate]:
        return {
            drone.claimed_cell
            for drone in self.peer_drones.values()
            if drone.alive and drone.reachable and drone.claimed_cell is not None
        }

    def _publish_heartbeat(self) -> None:
        if not self.local_drone.alive or not self.local_drone.reachable:
            return
        self.heartbeat.beat(self.local_drone.drone_id, now_ms=self.now_ms)
        self.mesh.publish(
            heartbeat_topic(self.local_drone.drone_id),
            make_heartbeat_payload(drone_id=self.local_drone.drone_id, position=self.local_drone.position),
            timestamp_ms=self.now_ms,
            sender_id=self.config.peer_id,
        )

    def _publish_state(self) -> None:
        self.mesh.publish(
            drone_state_topic(self.local_drone.drone_id),
            make_drone_state_payload(
                drone_id=self.local_drone.drone_id,
                position=self.local_drone.position,
                target=self.local_drone.target_cell,
                status=self.local_drone.status,
                alive=self.local_drone.alive,
                reachable=self.local_drone.reachable,
                claimed_cell=self.local_drone.claimed_cell,
                searched_cells=self.local_drone.searched_cells,
            ),
            timestamp_ms=self.now_ms,
            sender_id=self.config.peer_id,
        )

    def _handle_heartbeat(self, envelope: MeshEnvelope) -> None:
        payload = envelope.payload
        drone_id = str(payload["drone_id"])
        position = (int(payload["position"][0]), int(payload["position"][1]))
        peer = self._ensure_peer(drone_id, position=position)
        was_stale = not peer.reachable or not peer.alive or drone_id in self._stale_since_ms
        peer.alive = True
        peer.reachable = True
        self.heartbeat.beat(drone_id, now_ms=envelope.timestamp_ms)
        if was_stale:
            self._stale_since_ms.pop(drone_id, None)
            self._log("peer_recovered", f"{drone_id} resumed heartbeating", drone_id=drone_id)

    def _handle_drone_state(self, envelope: MeshEnvelope) -> None:
        payload = parse_drone_state_payload(envelope.payload)
        peer = self._ensure_peer(payload.drone_id, position=payload.position)
        peer.position = payload.position
        peer.target_cell = payload.target
        peer.claimed_cell = payload.claimed_cell
        peer.status = payload.status  # type: ignore[assignment]
        peer.alive = payload.alive
        peer.reachable = payload.reachable
        peer.searched_cells = payload.searched_cells

    def _handle_claim(self, envelope: MeshEnvelope) -> None:
        payload = parse_claim_payload(envelope.payload)
        if payload.claim_id in self._resolved_claim_ids:
            return
        self._pending_claims[payload.claim_id] = ClaimRequest(
            claim_id=payload.claim_id,
            drone_id=payload.drone_id,
            cell=payload.cell,
            position=payload.position,
            timestamp_ms=payload.timestamp_ms,
        )
        self._ensure_peer(payload.drone_id, position=payload.position).status = "claiming"

    def _apply_round(self, round_payload: BftRoundPayload) -> None:
        if round_payload.round_id in self._processed_rounds:
            return
        self._processed_rounds.add(round_payload.round_id)
        self.bft._round_id = max(self.bft._round_id, round_payload.round_id)
        self._append_proof(round_payload)
        if round_payload.released_by is not None:
            stale_peer = self._ensure_peer(round_payload.released_by)
            stale_peer.mark_stale()
            self._stale_since_ms[round_payload.released_by] = self.now_ms
        if len(round_payload.assignments) > 1:
            self.auctions += 1
        for assignment in round_payload.assignments:
            drone = self._ensure_peer(assignment.drone_id)
            if assignment.reason == "idle":
                drone.clear_assignment()
            else:
                drone.set_assignment(assignment.cell, subzone=assignment.subzone)
                drone.status = "claim_won" if assignment.drone_id == self.config.peer_id else drone.status
        self._log("bft", f"round {round_payload.round_id} resolved {round_payload.cell}")

    def _handle_bft_round(self, envelope: MeshEnvelope) -> None:
        self._apply_round(parse_bft_round_payload(envelope.payload))

    def _handle_certainty_update(self, envelope: MeshEnvelope) -> None:
        if envelope.topic.startswith("swarm/certainty_map/") and envelope.payload.get("grid") is not None:
            drone_id = str(envelope.payload.get("peer_id", envelope.sender_id))
            peer_map = self._ensure_peer_map(drone_id)
            peer_map.replace_from_rows(envelope.payload["grid"])
            for cell in peer_map:
                if cell.certainty > 0.5:
                    self.visited_cells.add(cell.coordinate)
                if cell.certainty >= self.config.completion_certainty:
                    self.completed_cells.add(cell.coordinate)
            self._recompute_merged_map()
            return

        payload = parse_certainty_payload(envelope.payload)
        target_map = self.local_map if payload.updated_by == self.config.peer_id else self._ensure_peer_map(payload.updated_by)
        current = target_map.cell(payload.cell).certainty
        target_map.set_certainty(
            payload.cell,
            max(current, payload.certainty),
            updated_by=payload.updated_by,
            now_ms=envelope.timestamp_ms,
        )
        if payload.certainty > 0.5:
            self.visited_cells.add(payload.cell)
        if payload.certainty >= self.config.completion_certainty:
            self.completed_cells.add(payload.cell)
        self._recompute_merged_map()

    def _handle_survivor(self, envelope: MeshEnvelope) -> None:
        payload = parse_survivor_payload(envelope.payload)
        self.survivor_found = True
        self._log("survivor", f"survivor found by {payload.drone_id} at {payload.cell}")
        if payload.drone_id != self.config.peer_id:
            self.mesh.publish(
                survivor_ack_topic(self.config.peer_id),
                {
                    "drone_id": self.config.peer_id,
                    "source_drone_id": payload.drone_id,
                    "cell": list(payload.cell),
                },
                timestamp_ms=self.now_ms,
                sender_id=self.config.peer_id,
            )

    def _handle_survivor_ack(self, envelope: MeshEnvelope) -> None:
        drone_id = str(envelope.payload["drone_id"])
        self.survivor_receipts.add(drone_id)

    def process_incoming_messages(self) -> None:
        for envelope in self.mesh.poll():
            topic = envelope.topic
            if topic.startswith("swarm/heartbeat/"):
                self._handle_heartbeat(envelope)
            elif topic.startswith("swarm/drone_state/"):
                self._handle_drone_state(envelope)
            elif topic == "swarm/zone_claims":
                self._handle_claim(envelope)
            elif topic.startswith("swarm/bft_result/"):
                self._handle_bft_round(envelope)
            elif topic.startswith("swarm/certainty_map"):
                self._handle_certainty_update(envelope)
            elif topic == "swarm/survivor_found":
                self._handle_survivor(envelope)
            elif topic.startswith("swarm/survivor_found_ack/"):
                self._handle_survivor_ack(envelope)

    def _detect_stale_peers(self) -> None:
        timeout_ms = max(
            self.config.stale_after_seconds * 1000,
            self._tick_ms() * STALE_TIMEOUT_TICK_MULTIPLIER,
        )
        status = self.heartbeat.detect_stale(
            now_ms=self.now_ms,
            timeout_ms=timeout_ms,
        )
        for drone_id in status.stale:
            if drone_id == self.config.peer_id:
                continue
            peer = self._ensure_peer(drone_id)
            if not peer.alive:
                continue
            if self._is_coordinator() and drone_id not in self._released_stale and peer.claimed_cell is not None:
                release_round = self.bft.confirm_release(drone_id=drone_id, cell=peer.claimed_cell)
                payload = make_bft_round_payload(
                    round_id=release_round.round_id,
                    contest_id=release_round.contest_id,
                    cell=release_round.cell,
                    assignments=[],
                    rationale=release_round.rationale,
                    released_by=drone_id,
                )
                self.mesh.publish(
                    bft_round_topic(release_round.round_id),
                    payload,
                    timestamp_ms=self.now_ms,
                    sender_id=self.config.peer_id,
                )
                self._apply_round(parse_bft_round_payload(payload))
                self._released_stale.add(drone_id)
            peer.mark_stale()
            self._stale_since_ms[drone_id] = self.now_ms

    def _claim_resolution_delay_ms(self) -> int:
        return self._tick_ms() * (2 if self.config.transport == "foxmq" else 1)

    def _resolve_pending_claims(self) -> None:
        if not self._is_coordinator():
            return
        mature_claims = [
            claim
            for claim in self._pending_claims.values()
            if claim.timestamp_ms <= self.now_ms - self._claim_resolution_delay_ms()
            and claim.claim_id not in self._resolved_claim_ids
        ]
        grouped: dict[Coordinate, list[ClaimRequest]] = {}
        for claim in mature_claims:
            grouped.setdefault(claim.cell, []).append(claim)
        for cell in sorted(grouped):
            result: BftRoundResult = self.bft.resolve_claims(
                grouped[cell],
                certainty_map=self.certainty_map,
                selector=self.selector,
                claimed_zones=self._claimed_zones(),
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
            payload = make_bft_round_payload(
                round_id=result.round_id,
                contest_id=result.contest_id,
                cell=result.cell,
                assignments=assignments,
                rationale=result.rationale,
            )
            self.mesh.publish(
                bft_round_topic(result.round_id),
                payload,
                timestamp_ms=self.now_ms,
                sender_id=self.config.peer_id,
            )
            self._apply_round(parse_bft_round_payload(payload))
            self._resolved_claim_ids.update(claim.claim_id for claim in grouped[cell])
        for claim_id in list(self._pending_claims):
            if claim_id in self._resolved_claim_ids:
                del self._pending_claims[claim_id]

    def _inject_failure(self) -> None:
        event = self.failure_injector.maybe_trigger([self.local_drone], now_seconds=self.now_ms // 1000)
        if event is not None:
            self._log("failure", f"{event.drone_id} dropped off-mesh", mode=event.mode)
            raise PeerFailureExit(f"{event.drone_id} dropped off-mesh", exit_code=2)

    def _maybe_claim_zone(self) -> None:
        if (self.survivor_found and self.config.stop_on_survivor) or not self.local_drone.alive or not self.local_drone.reachable:
            return
        if self.local_drone.target_cell is not None:
            return
        self.local_drone.status = "computing"
        claimed_zones = self._claimed_zones()
        if self.now_ms <= self._tick_ms() * 3 and not self._processed_rounds:
            claimed_zones = set()
        blocked = (
            set(self.completed_cells)
            if len(self.completed_cells) < self.config.grid * self.config.grid
            else set()
        )
        selection = self.selector.select_next_zone(
            self.certainty_map,
            claimed_zones=claimed_zones,
            blocked_zones=blocked,
            current_position=self.local_drone.position,
        )
        if self._should_force_target_probe(claimed_zones, blocked):
            selection = None
            selection = type("ZoneSelectionProxy", (), {
                "coordinate": self.config.target,
                "certainty": self.certainty_map.cell(self.config.target).certainty,
                "entropy": self.certainty_map.entropy_at(self.config.target),
                "distance": 0.0,
            })()
        if selection is None:
            self.local_drone.status = "idle"
            return
        claim = ClaimRequest(
            claim_id=f"{self.config.peer_id}:{selection.coordinate[0]}:{selection.coordinate[1]}:{self.now_ms}",
            drone_id=self.config.peer_id,
            cell=selection.coordinate,
            position=self.local_drone.position,
            timestamp_ms=self.now_ms,
        )
        self.local_drone.status = "claiming"
        self._pending_claims[claim.claim_id] = claim
        self.mesh.publish(
            "swarm/zone_claims",
            make_claim_payload(
                claim_id=claim.claim_id,
                drone_id=claim.drone_id,
                cell=claim.cell,
                position=claim.position,
                timestamp_ms=claim.timestamp_ms,
            ),
            timestamp_ms=self.now_ms,
            sender_id=self.config.peer_id,
        )
        self._log("claim", f"{self.config.peer_id} targeting {selection.coordinate}", claim_id=claim.claim_id)

    def _move_and_search(self) -> None:
        drone = self.local_drone
        if not drone.alive or not drone.reachable:
            return
        if drone.status in {"claim_won", "claim_lost", "claiming", "computing"} and drone.target_cell is not None:
            drone.status = "transiting" if drone.position != drone.target_cell else "searching"
        if drone.target_cell is None:
            drone.status = "idle"
            return
        if drone.position != drone.target_cell:
            drone.position = drone.target_cell
            drone.status = "searching"
        drone.status = "searching"
        updated = self.local_map.update_cell(
            drone.target_cell,
            updated_by=drone.drone_id,
            increment=self.config.search_increment,
            now_ms=self.now_ms,
        )
        self._recompute_merged_map()
        drone.searched_cells += 1
        self.mesh.publish(
            "swarm/certainty_map",
            make_certainty_payload(
                updated_by=drone.drone_id,
                cell=updated.coordinate,
                certainty=updated.certainty,
            ),
            timestamp_ms=self.now_ms,
            sender_id=self.config.peer_id,
        )
        self._publish_local_map_snapshot()
        if drone.target_cell == self.config.target and updated.certainty >= self.config.completion_certainty:
            self.survivor_found = True
            self.mesh.publish(
                "swarm/survivor_found",
                make_survivor_payload(
                    drone_id=drone.drone_id,
                    cell=updated.coordinate,
                    confidence=round(updated.certainty, 3),
                ),
                timestamp_ms=self.now_ms,
                sender_id=self.config.peer_id,
            )
        if updated.certainty >= self.config.completion_certainty:
            self.completed_cells.add(updated.coordinate)
            drone.clear_assignment()
        if updated.certainty > 0.5:
            self.visited_cells.add(updated.coordinate)
        self._publish_state()

    def bootstrap(self) -> None:
        self._apply_runtime_control()
        self._log("mesh", f"peer runtime online via {self.config.transport} at {self.peer_address[0]}:{self.peer_address[1]}")
        self._publish_heartbeat()
        self._publish_local_map_snapshot()
        self._publish_state()
        if self.config.final_map_path:
            self.save_final_map(Path(self.config.final_map_path))

    def tick(self) -> None:
        self._apply_runtime_control()
        self.now_ms += self._tick_ms()
        self.process_incoming_messages()
        self._inject_failure()
        self._publish_heartbeat()
        if (self.now_ms // self._tick_ms()) % self.config.map_publish_interval == 0:
            self._publish_local_map_snapshot()
        self._detect_stale_peers()
        self.local_map.decay_all(seconds=self._tick_seconds, now_ms=self.now_ms)
        for peer_map in self.peer_maps.values():
            peer_map.decay_all(seconds=self._tick_seconds, now_ms=self.now_ms)
        self._recompute_merged_map()
        self._resolve_pending_claims()
        self.process_incoming_messages()
        self._move_and_search()
        if not (self.survivor_found and self.config.stop_on_survivor):
            self._maybe_claim_zone()
        self._publish_state()
        if self.config.final_map_path:
            self.save_final_map(Path(self.config.final_map_path))

    def _quiesce_claims(self) -> None:
        max_rounds = 12 if self.config.transport == "foxmq" else 3
        settled_rounds = 0
        for _ in range(max_rounds):
            self.now_ms += self._tick_ms()
            self.process_incoming_messages()
            self._publish_heartbeat()
            self._detect_stale_peers()
            self._resolve_pending_claims()
            self.process_incoming_messages()
            self._publish_state()
            time.sleep(self._tick_delay_seconds)
            if not self._pending_claims and all(drone.status != "claiming" for drone in self.peer_drones.values()):
                settled_rounds += 1
                if settled_rounds >= 2:
                    break
            else:
                settled_rounds = 0

    def summary(self) -> dict[str, Any]:
        current_coverage = round(self.certainty_map.coverage(threshold=self.config.completion_certainty), 3)
        completed_coverage = round(
            len(self.completed_cells) / (self.config.grid * self.config.grid),
            3,
        )
        visited_coverage = round(
            len(self.visited_cells) / (self.config.grid * self.config.grid),
            3,
        )
        return {
            "peer_id": self.config.peer_id,
            "duration_elapsed": self.now_ms // 1000,
            "coverage": visited_coverage,
            "coverage_completed": completed_coverage,
            "coverage_current": current_coverage,
            "average_entropy": round(self.certainty_map.average_entropy(), 3),
            "bft_rounds": self.bft._round_id,
            "auctions": self.auctions,
            "dropouts": sum(1 for drone in self.peer_drones.values() if not drone.reachable),
            "survivor_found": self.survivor_found,
            "survivor_receipts": len(self.survivor_receipts),
            "mesh_messages": self.mesh.count(),
            "target": self.config.target,
            "mesh": self.config.transport,
            "tick_seconds": self._tick_seconds,
            "tick_delay_seconds": round(self._tick_delay_seconds, 3),
            "requested_drone_count": self._requested_drone_count,
            "drones": [
                {
                    "id": drone.drone_id,
                    "alive": drone.alive,
                    "reachable": drone.reachable,
                    "position": drone.position,
                    "target": drone.target_cell,
                    "status": drone.status,
                    "searched_cells": drone.searched_cells,
                }
                for drone in sorted(self.peer_drones.values(), key=lambda item: item.drone_id)
            ],
        }

    def save_final_map(self, path: Path) -> None:
        summary = self.summary()
        payload = {
            "summary": summary,
            "stats": {
                "coverage": summary["coverage_current"],
                "average_entropy": summary["average_entropy"],
                "auctions": summary["auctions"],
                "dropouts": summary["dropouts"],
                "bft_rounds": summary["bft_rounds"],
                "elapsed": summary["duration_elapsed"],
            },
            "config": self._runtime_config_payload(),
            "events": self.events,
            "grid": self.certainty_map.to_rows(),
            "local_grid": self.local_map.to_rows(),
        }
        path.write_text(json.dumps(payload, indent=2) + "\n")

    def run(self) -> dict[str, Any]:
        self.bootstrap()
        try:
            while self.now_ms < self.config.duration * 1000:
                self.tick()
                time.sleep(self._tick_delay_seconds)
                if self.survivor_found and self.config.stop_on_survivor:
                    break
            summary = self.summary()
            if self.config.final_map_path:
                self.save_final_map(Path(self.config.final_map_path))
            return summary
        except PeerFailureExit:
            if self.config.final_map_path:
                self.save_final_map(Path(self.config.final_map_path))
            raise
        finally:
            self.mesh.close()
