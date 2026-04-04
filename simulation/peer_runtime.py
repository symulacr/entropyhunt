from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from auction.protocol import ClaimRequest
from core.bft import BftCoordinator, BftRoundResult
from core.certainty_map import CertaintyMap, Coordinate
from core.heartbeat import HeartbeatRegistry
from core.mesh import LocalPeerMeshBus, MeshEnvelope
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


@dataclass(frozen=True, slots=True)
class PeerRuntimeConfig:
    peer_id: str
    host: str = "127.0.0.1"
    port: int = 0
    peers: tuple[PeerEndpoint, ...] = ()
    grid: int = 10
    duration: int = 180
    tick_seconds: int = 1
    search_increment: float = 0.12
    completion_certainty: float = 0.92
    decay_rate: float = 0.001
    stale_after_seconds: int = 3
    target: Coordinate = (7, 3)
    stop_on_survivor: bool = False
    fail_at: int | None = None
    final_map_path: str = ""


def _starting_position(peer_id: str, peer_ids: list[str], grid: int) -> Coordinate:
    positions = [
        (0, 0),
        (grid - 1, 0),
        (0, grid - 1),
        (grid - 1, grid - 1),
        (grid // 2, grid // 2),
    ]
    try:
        index = peer_ids.index(peer_id)
    except ValueError:
        index = 0
    if index < len(positions):
        return positions[index]
    return (index % grid, (index * 2) % grid)


class PeerRuntime:
    def __init__(self, config: PeerRuntimeConfig) -> None:
        self.config = config
        self.now_ms = 0
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
        self.certainty_map = CertaintyMap(
            config.grid,
            initial_certainty=0.5,
            decay_rate=config.decay_rate,
            now_ms=self.now_ms,
        )
        self.selector = ZoneSelector()
        self.bft = BftCoordinator(self.peer_ids or [config.peer_id])
        self.failure_injector = FailureInjector(
            FailurePlan(drone_id=config.peer_id, fail_at_seconds=config.fail_at, mode="peer-runtime")
        )
        self.events: list[dict[str, Any]] = []
        self.survivor_found = False
        self.survivor_receipts: set[str] = set()
        self._pending_claims: dict[str, ClaimRequest] = {}
        self._resolved_claim_ids: set[str] = set()
        self._processed_rounds: set[int] = set()
        self._released_stale: set[str] = set()

    @property
    def peer_address(self) -> tuple[str, int]:
        return self.mesh.bind_address

    def _tick_ms(self) -> int:
        return self.config.tick_seconds * 1000

    def _log(self, event_type: str, message: str, **data: Any) -> None:
        self.events.append({"t": self.now_ms // 1000, "type": event_type, "message": message, **data})

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

    def _coordinator_id(self) -> str:
        return min(self._known_peer_ids())

    def _is_coordinator(self) -> bool:
        return self.config.peer_id == self._coordinator_id()

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
        peer.alive = True
        peer.reachable = True
        self.heartbeat.beat(drone_id, now_ms=envelope.timestamp_ms)

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
        if round_payload.released_by is not None:
            stale_peer = self._ensure_peer(round_payload.released_by)
            stale_peer.mark_stale()
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
        payload = parse_certainty_payload(envelope.payload)
        self.certainty_map.set_certainty(
            payload.cell,
            payload.certainty,
            updated_by=payload.updated_by,
            now_ms=envelope.timestamp_ms,
        )

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
            elif topic.startswith("swarm/bft_round/"):
                self._handle_bft_round(envelope)
            elif topic == "swarm/certainty_map":
                self._handle_certainty_update(envelope)
            elif topic == "swarm/survivor_found":
                self._handle_survivor(envelope)
            elif topic.startswith("swarm/survivor_found_ack/"):
                self._handle_survivor_ack(envelope)

    def _detect_stale_peers(self) -> None:
        status = self.heartbeat.detect_stale(
            now_ms=self.now_ms,
            timeout_ms=self.config.stale_after_seconds * 1000,
        )
        for drone_id in status.stale:
            if drone_id == self.config.peer_id:
                continue
            peer = self._ensure_peer(drone_id)
            if not peer.alive:
                continue
            if self._is_coordinator() and drone_id not in self._released_stale and peer.claimed_cell is not None:
                release_round = self.bft.confirm_release(drone_id=drone_id, cell=peer.claimed_cell)
                self.mesh.publish(
                    bft_round_topic(release_round.round_id),
                    make_bft_round_payload(
                        round_id=release_round.round_id,
                        cell=release_round.cell,
                        assignments=[],
                        rationale=release_round.rationale,
                        released_by=drone_id,
                    ),
                    timestamp_ms=self.now_ms,
                    sender_id=self.config.peer_id,
                )
                self._released_stale.add(drone_id)
            peer.mark_stale()

    def _resolve_pending_claims(self) -> None:
        if not self._is_coordinator():
            return
        mature_claims = [
            claim
            for claim in self._pending_claims.values()
            if claim.timestamp_ms <= self.now_ms - self._tick_ms()
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
            self.mesh.publish(
                bft_round_topic(result.round_id),
                make_bft_round_payload(
                    round_id=result.round_id,
                    cell=result.cell,
                    assignments=assignments,
                    rationale=result.rationale,
                ),
                timestamp_ms=self.now_ms,
                sender_id=self.config.peer_id,
            )
            self._resolved_claim_ids.update(claim.claim_id for claim in grouped[cell])
        for claim_id in list(self._pending_claims):
            if claim_id in self._resolved_claim_ids:
                del self._pending_claims[claim_id]

    def _inject_failure(self) -> None:
        event = self.failure_injector.maybe_trigger([self.local_drone], now_seconds=self.now_ms // 1000)
        if event is not None:
            self._log("failure", f"{event.drone_id} dropped off-mesh", mode=event.mode)

    def _maybe_claim_zone(self) -> None:
        if self.survivor_found or not self.local_drone.alive or not self.local_drone.reachable:
            return
        if self.local_drone.target_cell is not None:
            return
        self.local_drone.status = "computing"
        selection = self.selector.select_next_zone(
            self.certainty_map,
            claimed_zones=self._claimed_zones(),
            current_position=self.local_drone.position,
        )
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
            drone.step_towards_target()
            self._publish_state()
            return
        drone.status = "searching"
        updated = self.certainty_map.update_cell(
            drone.target_cell,
            updated_by=drone.drone_id,
            increment=self.config.search_increment,
            now_ms=self.now_ms,
        )
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
            drone.clear_assignment()
        self._publish_state()

    def bootstrap(self) -> None:
        self._log("mesh", f"peer runtime online at {self.peer_address[0]}:{self.peer_address[1]}")
        self._publish_heartbeat()
        self._publish_state()

    def tick(self) -> None:
        self.now_ms += self._tick_ms()
        self.process_incoming_messages()
        self._inject_failure()
        self._publish_heartbeat()
        self._detect_stale_peers()
        self.certainty_map.decay_all(seconds=self.config.tick_seconds, now_ms=self.now_ms)
        self._resolve_pending_claims()
        self.process_incoming_messages()
        self._move_and_search()
        if not (self.survivor_found and self.config.stop_on_survivor):
            self._maybe_claim_zone()
        self._publish_state()

    def summary(self) -> dict[str, Any]:
        coverage = round(self.certainty_map.coverage(threshold=self.config.completion_certainty), 3)
        return {
            "peer_id": self.config.peer_id,
            "duration_elapsed": self.now_ms // 1000,
            "coverage": coverage,
            "coverage_completed": coverage,
            "coverage_current": coverage,
            "average_entropy": round(self.certainty_map.average_entropy(), 3),
            "bft_rounds": self.bft._round_id,
            "dropouts": sum(1 for drone in self.peer_drones.values() if not drone.reachable),
            "survivor_found": self.survivor_found,
            "survivor_receipts": len(self.survivor_receipts),
            "mesh_messages": self.mesh.count(),
            "target": self.config.target,
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
        payload = {
            "summary": self.summary(),
            "config": asdict(self.config),
            "events": self.events,
            "grid": self.certainty_map.to_rows(),
        }
        path.write_text(json.dumps(payload, indent=2) + "\n")

    def run(self) -> dict[str, Any]:
        self.bootstrap()
        total_ticks = self.config.duration // self.config.tick_seconds
        for _ in range(total_ticks):
            self.tick()
            if self.survivor_found and self.config.stop_on_survivor:
                break
        summary = self.summary()
        if self.config.final_map_path:
            self.save_final_map(Path(self.config.final_map_path))
        self.mesh.close()
        return summary
