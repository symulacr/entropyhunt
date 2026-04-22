
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from core.certainty import CertaintyMap, Coordinate
from core.consensus import DeterministicResolver
from core.heartbeat import HeartbeatRegistry
from core.mesh import FoxMQConfig, FoxMQMeshBus, LocalPeerConfig, LocalPeerMeshBus, MeshBusProtocol
from core.selector import ZoneSelection, ZoneSelector
from failure.injector import FailureInjector, FailurePlan
from failure.network_injector import NetworkInjector
from roles.drone import DroneState, spread_starting_position
from simulation.claim_manager import PeerClaimManager
from simulation.mesh_handler import PeerMeshHandler
from simulation.peer_config import PeerFailureError, PeerRuntimeConfig
from simulation.proof import PeerProofLogger
from simulation.protocol import (
    make_rejoin_payload,
    make_survivor_payload,
)

__all__ = ["PeerFailureError", "PeerRuntime", "PeerRuntimeConfig"]

LOCAL_TICK_DELAY_SECONDS = 0.1
_VISITED_THRESHOLD = 0.5
_QUIESCE_ROUNDS_FOXMQ = 12
_QUIESCE_ROUNDS_LOCAL = 3
_QUIESCE_SETTLE_COUNT = 2
_RECONNECT_BACKOFF_BASE_MS = 1000
_RECONNECT_BACKOFF_MAX_MS = 30000
_QUORUM_STALE_THRESHOLD_MS = 10000


class _PeerStatusHandler(BaseHTTPRequestHandler):
    __slots__ = ("_runtime",)

    def __init__(self, runtime: PeerRuntime, *args: Any, **kwargs: Any) -> None:
        self._runtime = runtime
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        if self.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            peers_seen = sorted(self._runtime.heartbeat._last_seen_ms.keys())
            payload = {
                "peer_id": self._runtime.config.peer_id,
                "peers_seen": peers_seen,
                "expected_peers": len(self._runtime.peer_ids),
                "mesh_peers": [
                    {"peer_id": pid, "last_seen_ms": ms}
                    for pid, ms in sorted(self._runtime.heartbeat._last_seen_ms.items())
                ],
            }
            self.wfile.write(json.dumps(payload).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        return


class PeerRuntime:

    def __init__(self, config: PeerRuntimeConfig) -> None:
        self.config = config
        self.now_ms = 0

        if config.transport == "foxmq":
            self.mesh: MeshBusProtocol = FoxMQMeshBus(
                peer_id=config.peer_id,
                config=FoxMQConfig(
                    mqtt_host=config.mqtt_host,
                    mqtt_port=config.mqtt_port,
                    username=config.mqtt_username,
                    password=config.mqtt_password,
                ),
            )
        else:
            self.mesh = LocalPeerMeshBus(
                peer_id=config.peer_id,
                config=LocalPeerConfig(
                    bind_host=config.host,
                    bind_port=config.port,
                    peer_addresses=[(peer.host, peer.port) for peer in config.peers],
                    discovery_enabled=config.discovery_enabled,
                ),
            )

        self._proof_logger = PeerProofLogger(config.proofs_path)
        if config.packet_loss > 0.0 or config.jitter_ms > 0.0:
            self.mesh = NetworkInjector(
                self.mesh,
                packet_loss=config.packet_loss,
                jitter_ms=config.jitter_ms,
                proof_logger=self._proof_logger,
            )
        self.peer_ids = sorted(
            {config.peer_id, *[peer.peer_id for peer in config.peers if peer.peer_id]},
        )

        self.local_drone = DroneState(
            drone_id=config.peer_id,
            position=spread_starting_position(
                config.peer_id,
                self.peer_ids or [config.peer_id],
                config.grid,
            ),
        )
        self.peer_drones: dict[str, DroneState] = {config.peer_id: self.local_drone}
        self.local_map = CertaintyMap(
            config.grid,
            initial_certainty=_VISITED_THRESHOLD,
            decay_rate=config.decay_rate,
            now_ms=self.now_ms,
        )
        self.peer_maps: dict[str, CertaintyMap] = {config.peer_id: self.local_map}
        self.certainty_map = self.local_map.clone()

        heartbeat = HeartbeatRegistry()
        self._mesh_handler = PeerMeshHandler(
            config=config,
            mesh=self.mesh,
            local_drone=self.local_drone,
            local_map=self.local_map,
            peer_maps=self.peer_maps,
            heartbeat=heartbeat,
            peer_drones=self.peer_drones,
        )
        self.mesh.subscribe(config.peer_id, "swarm/#")
        self._claim_manager = PeerClaimManager(
            config=config,
            mesh=self.mesh,
            resolver=DeterministicResolver(self.peer_ids or [config.peer_id]),
            selector=ZoneSelector(),
            mesh_handler=self._mesh_handler,
            proof_logger=self._proof_logger,
        )

        self.failure_injector = FailureInjector(
            FailurePlan(
                drone_id=config.peer_id,
                fail_at_seconds=config.fail_at,
                mode="peer-runtime",
            ),
        )
        self._forced_target_probe_logged = False
        env_tick_delay = os.environ.get("ENTROPYHUNT_TICK_DELAY_SECONDS")
        configured_delay = config.tick_delay_seconds
        if configured_delay is not None:
            self._tick_delay_seconds = max(0.0, float(configured_delay))
        elif env_tick_delay is not None:
            self._tick_delay_seconds = max(0.0, float(env_tick_delay))
        else:
            self._tick_delay_seconds = LOCAL_TICK_DELAY_SECONDS
        self._tick_seconds = max(1, int(config.tick_seconds))
        self._control_file = Path(config.control_file) if config.control_file else None
        self._control_mtime_ns: int | None = None
        self._requested_drone_count = len(self.peer_ids or [config.peer_id])
        self._peer_status = "HEALTHY"
        self._degraded_since_ms: int | None = None
        self._reconnect_attempt = 0
        self._next_reconnect_at_ms: int | None = None
        self._status_server: ThreadingHTTPServer | None = None
        self._status_thread: threading.Thread | None = None
        self._start_status_server()

    def _start_status_server(self) -> None:
        port = self.config.control_port
        if port <= 0:
            if isinstance(self.mesh, LocalPeerMeshBus):
                port = self.mesh.bind_address[1]
            else:
                return
        host = self.config.host if self.config.host not in ("", "0.0.0.0") else "127.0.0.1"
        try:
            server = ThreadingHTTPServer(
                (host, port),
                lambda *a, **kw: _PeerStatusHandler(self, *a, **kw),
            )
            self._status_server = server
            self._status_thread = threading.Thread(target=server.serve_forever, daemon=True)
            self._status_thread.start()
        except Exception as exc:
            self._log("status_server", f"failed to start status server on {host}:{port}: {exc}")

    @property
    def heartbeat(self) -> HeartbeatRegistry:
        return self._mesh_handler.heartbeat

    @property
    def events(self) -> list[dict[str, Any]]:
        return self._proof_logger.events

    @property
    def completed_cells(self) -> set[Coordinate]:
        return self._mesh_handler.completed_cells

    @property
    def visited_cells(self) -> set[Coordinate]:
        return self._mesh_handler.visited_cells

    @property
    def survivor_found(self) -> bool:
        return self._mesh_handler.survivor_found

    @survivor_found.setter
    def survivor_found(self, value: bool) -> None:
        self._mesh_handler.survivor_found = value

    @property
    def survivor_receipts(self) -> set[str]:
        return self._mesh_handler.survivor_receipts

    @property
    def auctions(self) -> int:
        return self._claim_manager.auctions

    @property
    def resolver(self) -> DeterministicResolver:
        return self._claim_manager.resolver

    @property
    def proofs_path(self) -> Path:
        return self._proof_logger.proofs_path

    @property
    def peer_address(self) -> tuple[str, int]:
        if isinstance(self.mesh, LocalPeerMeshBus):
            return self.mesh.bind_address
        return (self.config.mqtt_host, self.config.mqtt_port)

    def _tick_ms(self) -> int:
        return self._tick_seconds * 1000

    def _runtime_config_payload(self) -> dict[str, Any]:
        payload = asdict(self.config)
        payload["tick_seconds"] = self._tick_seconds
        payload["tick_delay_seconds"] = self._tick_delay_seconds
        payload["requested_drone_count"] = self._requested_drone_count
        payload["source_mode"] = "peer"
        payload["snapshot_provenance"] = "peer-runtime-export"
        payload["synthetic"] = False
        payload["control_capabilities"] = {
            "tick_seconds": "live" if self._control_file is not None else "unavailable",
            "tick_delay_seconds": "live" if self._control_file is not None else "unavailable",
            "requested_drone_count": "next_run"
            if self._control_file is not None
            else "unavailable",
        }
        payload["control_path"] = str(self._control_file) if self._control_file is not None else ""
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
        if (
            isinstance(next_tick_seconds, int)
            and next_tick_seconds > 0
            and next_tick_seconds != self._tick_seconds
        ):
            self._tick_seconds = next_tick_seconds
            changed = True
        if isinstance(next_tick_delay, (int, float)):
            next_delay = max(0.0, float(next_tick_delay))
            if next_delay != self._tick_delay_seconds:
                self._tick_delay_seconds = next_delay
                changed = True
        if (
            isinstance(next_requested_count, int)
            and next_requested_count > 0
            and next_requested_count != self._requested_drone_count
        ):
            self._requested_drone_count = next_requested_count
            changed = True
        if changed:
            self._log(
                "config",
                f"runtime config updated: tick={self._tick_seconds}s "
                f"delay={self._tick_delay_seconds:.2f}s "
                f"requested_drones={self._requested_drone_count}",
            )

    def _log(self, event_type: str, message: str, **data: object) -> None:
        self._proof_logger.log(self.now_ms // 1000, event_type, message, **data)

    def _recompute_merged_map(self, *, force: bool = False) -> None:
        result = self._mesh_handler.recompute_merged_map(self.certainty_map, force=force)
        if result is not None:
            self.certainty_map = result

    def process_incoming_messages(self) -> None:
        certainty_changed = self._mesh_handler.process_incoming_messages(
            now_ms=self.now_ms,
            log_fn=self._log,
            claim_fn=self._claim_manager.handle_claim,
            round_fn=lambda env: self._claim_manager.handle_consensus_round(
                env,
                self.now_ms,
                log_fn=self._log,
            ),
        )
        if certainty_changed:
            self._recompute_merged_map()

    def _detect_stale_peers(self) -> None:
        self._claim_manager.detect_stale_peers(self.now_ms, self._tick_ms(), self._log)

    def _resolve_pending_claims(self) -> None:
        self._claim_manager.resolve_pending_claims(
            self.now_ms,
            self._tick_ms(),
            self.certainty_map,
            self._log,
        )

    def _inject_failure(self) -> None:
        event = self.failure_injector.maybe_trigger(
            [self.local_drone],
            now_seconds=self.now_ms // 1000,
        )
        if event is not None:
            self._log("failure", f"{event.drone_id} dropped off-mesh", mode=event.mode)
            if self._peer_status == "HEALTHY":
                self.local_drone.reachable = False
                self._peer_status = "DEGRADED"
                self._degraded_since_ms = self.now_ms
                self._reconnect_attempt = 0
                self._next_reconnect_at_ms = self.now_ms + _RECONNECT_BACKOFF_BASE_MS
                self._log(
                    "degraded",
                    f"{event.drone_id} entering degraded mode",
                    drone_id=event.drone_id,
                )

    def _inject_partition_failure(self) -> None:
        event = self.failure_injector.maybe_trigger(
            [self.local_drone],
            now_seconds=self.now_ms // 1000,
        )
        if event is not None:
            self.local_drone.reachable = False
            self._log(
                "partition",
                f"{event.drone_id} partitioned (reachable=False, alive=True)",
                mode="partition",
            )

    def _attempt_reconnect(self) -> bool:
        if isinstance(self.mesh, FoxMQMeshBus):
            if not self.mesh._connected.is_set():
                try:
                    self.mesh.connect()
                except Exception as exc:
                    self._log("reconnect_failed", f"FoxMQ reconnect failed: {exc}")
                    return False
        self.local_drone.reachable = True
        self._peer_status = "HEALTHY"
        self._degraded_since_ms = None
        self._next_reconnect_at_ms = None
        self._reconnect_attempt = 0
        return True

    def _update_quorum(self) -> None:
        active_peers = [self.config.peer_id]
        for peer_id in self.peer_ids:
            if peer_id == self.config.peer_id:
                continue
            if self.heartbeat.is_stale(
                peer_id, now_ms=self.now_ms, timeout_ms=_QUORUM_STALE_THRESHOLD_MS,
            ):
                continue
            active_peers.append(peer_id)
        current_peers = list(self._claim_manager.resolver.peer_ids)
        if sorted(active_peers) != sorted(current_peers):
            self._claim_manager.resolver.set_peer_ids(active_peers)
            self._log("quorum_adjusted", "quorum peers updated", peers=active_peers)

    def _maybe_claim_zone(self) -> None:
        if (
            (self.survivor_found and self.config.stop_on_survivor)
            or not self.local_drone.alive
            or not self.local_drone.reachable
        ):
            return
        if self.local_drone.target_cell is not None:
            return
        self.local_drone.status = "computing"
        claimed_zones = self._mesh_handler.claimed_zones()
        if self.now_ms <= self._tick_ms() * 3 and not self._claim_manager.has_processed_rounds:
            claimed_zones = set()
        blocked = (
            set(self.completed_cells)
            if len(self.completed_cells) < self.config.grid * self.config.grid
            else set()
        )
        selection = self._claim_manager.selector.select_next_zone(
            self.certainty_map,
            claimed_zones=claimed_zones,
            blocked_zones=blocked,
            current_position=self.local_drone.position,
        )
        if self._should_force_target_probe(claimed_zones, blocked):
            if not self._forced_target_probe_logged:
                self._log(
                    "forced_target_probe",
                    "target probe forced after timeout to keep the demo converging",
                    target=list(self.config.target),
                    after_ms=self.config.target_force_at_s * 1000,
                )
                self._forced_target_probe_logged = True
            selection = ZoneSelection(
                coordinate=self.config.target,
                certainty=self.certainty_map.cell(self.config.target).certainty,
                entropy=self.certainty_map.entropy_at(self.config.target),
                distance=0.0,
            )
        if selection is None:
            self.local_drone.status = "idle"
            return
        self.local_drone.status = "claiming"
        self._claim_manager.build_and_publish_claim(
            selection.coordinate,
            self.now_ms,
            self.local_drone.position,
            self._log,
        )

    def _should_force_target_probe(
        self,
        claimed_zones: set[Coordinate],
        blocked_zones: set[Coordinate],
    ) -> bool:
        target_force_ms = self.config.target_force_at_s * 1000
        return (
            not self.survivor_found
            and self.now_ms >= target_force_ms
            and self.config.target not in claimed_zones
            and self.config.target not in blocked_zones
        )

    def _move_and_search(self) -> None:
        drone = self.local_drone
        if not drone.alive or not drone.reachable:
            return
        if (
            drone.status in {"claim_won", "claim_lost", "claiming", "computing"}
            and drone.target_cell is not None
        ):
            drone.status = "transiting" if drone.position != drone.target_cell else "searching"
        if drone.target_cell is None:
            drone.status = "idle"
            return
        if drone.position != drone.target_cell:
            drone.step_towards_target()
            self._mesh_handler.publish_state(self.now_ms)
            return
        drone.status = "searching"
        updated = self.local_map.update_cell(
            drone.target_cell,
            updated_by=drone.drone_id,
            increment=self.config.search_increment,
            now_ms=self.now_ms,
        )
        self._mesh_handler.mark_peer_maps_dirty()
        self._recompute_merged_map()
        drone.searched_cells += 1
        self._mesh_handler.publish_certainty_delta(
            updated.coordinate,
            updated.certainty,
            drone.drone_id,
            self.now_ms,
        )
        self._mesh_handler.publish_local_map_snapshot(self.now_ms)
        if (
            drone.target_cell == self.config.target
            and updated.certainty >= self.config.completion_certainty
        ):
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
        if updated.certainty > _VISITED_THRESHOLD:
            self.visited_cells.add(updated.coordinate)
        self._mesh_handler.publish_state(self.now_ms)

    def bootstrap(self) -> None:
        self._apply_runtime_control()
        self._log(
            "mesh",
            f"peer runtime online via {self.config.transport} "
            f"at {self.peer_address[0]}:{self.peer_address[1]}",
        )
        self._mesh_handler.publish_heartbeat(self.now_ms)
        self._mesh_handler.publish_local_map_snapshot(self.now_ms)
        self._mesh_handler.publish_state(self.now_ms)

    def tick(self) -> None:
        self._apply_runtime_control()
        self.now_ms += self._tick_ms()
        if self.config.failure_mode == "partition":
            self._inject_partition_failure()
        else:
            self._inject_failure()

        if self._peer_status == "DEGRADED" and self._next_reconnect_at_ms is not None:
            if self.now_ms >= self._next_reconnect_at_ms:
                self._peer_status = "RECONNECTING"
                if self._attempt_reconnect():
                    self.mesh.publish(
                        f"swarm/rejoin/{self.config.peer_id}",
                        make_rejoin_payload(
                            drone_id=self.config.peer_id, recovered_at_ms=self.now_ms,
                        ),
                        timestamp_ms=self.now_ms,
                        sender_id=self.config.peer_id,
                    )
                    self._log(
                        "recovery",
                        f"{self.config.peer_id} rejoined mesh",
                        drone_id=self.config.peer_id,
                    )
                    self._mesh_handler.publish_local_map_snapshot(self.now_ms)
                    self._mesh_handler.publish_state(self.now_ms)
                else:
                    self._peer_status = "DEGRADED"
                    self._reconnect_attempt += 1
                    backoff = min(
                        _RECONNECT_BACKOFF_BASE_MS * (2**self._reconnect_attempt),
                        _RECONNECT_BACKOFF_MAX_MS,
                    )
                    self._next_reconnect_at_ms = self.now_ms + backoff

        self._mesh_handler.publish_heartbeat(self.now_ms, peer_status=self._peer_status)
        if (self.now_ms // self._tick_ms()) % self.config.map_publish_interval == 0:
            self._mesh_handler.publish_local_map_snapshot(self.now_ms)
        self._detect_stale_peers()
        self._update_quorum()
        self.local_map.decay_all(seconds=self._tick_seconds, now_ms=self.now_ms)
        for drone_id, peer_map in list(self.peer_maps.items()):
            if drone_id == self.config.peer_id:
                continue
            peer_drone = self.peer_drones.get(drone_id)
            if peer_drone is not None and (not peer_drone.alive or not peer_drone.reachable):
                continue
            peer_map.decay_all(seconds=self._tick_seconds, now_ms=self.now_ms)
        self._mesh_handler.mark_peer_maps_dirty()
        self._recompute_merged_map(force=True)
        self.process_incoming_messages()
        self._resolve_pending_claims()
        self._move_and_search()
        if not (self.survivor_found and self.config.stop_on_survivor):
            self._maybe_claim_zone()
        self._mesh_handler.publish_state(self.now_ms)

    def _quiesce_claims(self) -> None:
        max_rounds = (
            _QUIESCE_ROUNDS_FOXMQ if self.config.transport == "foxmq" else _QUIESCE_ROUNDS_LOCAL
        )
        settled_rounds = 0
        for _ in range(max_rounds):
            self.now_ms += self._tick_ms()
            self._mesh_handler.publish_heartbeat(self.now_ms)
            self._detect_stale_peers()
            self._resolve_pending_claims()
            self.process_incoming_messages()
            self._mesh_handler.publish_state(self.now_ms)
            time.sleep(self._tick_delay_seconds)
            if (
                not self._claim_manager.has_pending_claims()
                and not self._claim_manager.any_drone_claiming()
            ):
                settled_rounds += 1
                if settled_rounds >= _QUIESCE_SETTLE_COUNT:
                    break
            else:
                settled_rounds = 0

    def summary(self) -> dict[str, Any]:
        current_coverage = round(
            self.certainty_map.coverage(threshold=self.config.completion_certainty),
            3,
        )
        completed_coverage = round(
            len(self.completed_cells) / (self.config.grid * self.config.grid),
            3,
        )
        visited_coverage = round(
            len(self.visited_cells) / (self.config.grid * self.config.grid),
            3,
        )
        elapsed_seconds = self.now_ms // 1000
        heartbeat_status = self.heartbeat.detect_stale(
            now_ms=self.now_ms,
            timeout_ms=max(
                self.config.stale_after_seconds * 1000,
                self._tick_ms() * self.config.stale_timeout_tick_multiplier,
            ),
        )
        recent_events = self.events[-200:] if len(self.events) > 200 else list(self.events)
        consensus_rounds: list[dict[str, Any]] = []
        seen_contest_ids: set[str] = set()
        for event in reversed(recent_events):
            if event.get("type") == "consensus_result":
                contest_id = str(event.get("contest_id", ""))
                if not contest_id or contest_id in seen_contest_ids:
                    continue
                seen_contest_ids.add(contest_id)
                consensus_rounds.append({
                    "round_id": event.get("round_id", 0),
                    "contest_id": contest_id,
                    "cell": event.get("cell"),
                    "vote_count": len(event.get("assignments", [])),
                    "status": "resolved",
                })
            if len(consensus_rounds) >= 20:
                break
        consensus_rounds.reverse()
        failures: list[dict[str, Any]] = []
        seen_failure_keys: set[tuple[str, int]] = set()
        for event in recent_events:
            event_type = str(event.get("type", ""))
            if event_type in ("failure", "partition", "peer_dropped", "stale", "heartbeat_timeout"):
                drone_id = str(event.get("drone_id") or event.get("peer_id") or "")
                t = int(event.get("t", 0))
                key = (drone_id, t)
                if key not in seen_failure_keys:
                    seen_failure_keys.add(key)
                    failures.append({
                        "drone_id": drone_id,
                        "failure_type": event_type,
                        "recovered": False,
                        "t": t,
                    })
            elif event_type == "peer_recovered":
                drone_id = str(event.get("drone_id") or event.get("peer_id") or "")
                for f in failures:
                    if f["drone_id"] == drone_id and not f["recovered"]:
                        f["recovered"] = True
        mesh_peers = [
            {
                "peer_id": peer_id,
                "last_seen_ms": last_seen,
                "stale": peer_id in heartbeat_status.stale,
            }
            for peer_id, last_seen in sorted(self.heartbeat._last_seen_ms.items())
        ]
        pending_claims = [
            {
                "claim_id": claim.claim_id,
                "zone": list(claim.cell),
                "owner": claim.drone_id,
                "timestamp_ms": claim.timestamp_ms,
            }
            for claim in sorted(
                self._claim_manager._pending_claims.values(),
                key=lambda c: c.timestamp_ms,
            )
        ]
        return {
            "peer_id": self.config.peer_id,
            "duration_elapsed": elapsed_seconds,
            "coverage": completed_coverage,
            "coverage_completed": completed_coverage,
            "coverage_current": current_coverage,
            "coverage_visited": visited_coverage,
            "average_entropy": round(self.certainty_map.average_entropy(), 3),
            "consensus_rounds": self._claim_manager.round_id,
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
                    "claimed_cell": drone.claimed_cell,
                    "claim_zone": drone.claimed_cell,
                    "status": drone.status,
                    "searched_cells": drone.searched_cells,
                    "role": drone.role,
                    "subzone": drone.subzone,
                    "battery": round(max(0.0, 100.0 - elapsed_seconds * 0.15 - drone.searched_cells * 0.8), 1),
                }
                for drone in sorted(self.peer_drones.values(), key=lambda item: item.drone_id)
            ],
            "mesh_peers": mesh_peers,
            "pending_claims": pending_claims,
            "consensus": consensus_rounds,
            "peer_status": self._peer_status,
            "failures": failures,
        }

    def save_final_map(self, path: Path) -> None:
        summary = self.summary()
        claimed_owner_map = self._mesh_handler.claimed_owner_map()
        payload = {
            "summary": summary,
            "stats": {
                "coverage": summary["coverage_current"],
                "average_entropy": summary["average_entropy"],
                "auctions": summary["auctions"],
                "dropouts": summary["dropouts"],
                "consensus_rounds": summary["consensus_rounds"],
                "elapsed": summary["duration_elapsed"],
            },
            "config": self._runtime_config_payload(),
            "events": self.events,
            "grid": self.certainty_map.to_rows(claimed_owner_map),
            "local_grid": self.local_map.to_rows(claimed_owner_map),
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
        finally:
            if self.config.final_map_path:
                self.save_final_map(Path(self.config.final_map_path))
            self._proof_logger.close()
            poc_path = Path(self.config.proofs_path).with_name("proof_of_coordination.json")
            self._proof_logger.finalize(poc_path, mesh_transport=self.config.transport)
            if self._status_server is not None:
                self._status_server.shutdown()
            if self._status_thread is not None:
                self._status_thread.join(timeout=1.0)
            self.mesh.close()
        return self.summary()
