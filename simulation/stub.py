
from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from auction.protocol import ClaimRequest, ZoneAssignment
from core.certainty import CertaintyMap, Coordinate, shannon_entropy
from core.consensus import ConsensusRoundResult, DeterministicResolver, ResolveClaimsRequest
from core.heartbeat import HeartbeatRegistry
from core.mesh import InMemoryMeshBus, VertexMeshBus
from core.selector import ZoneSelector
from failure.injector import FailureInjector, FailurePlan
from failure.network_injector import NetworkInjector
from roles.drone import DroneState, spread_starting_position
from simulation.base_config import BaseSimulationConfig
from simulation.export import SnapshotExporter
from simulation.proof import ProofLogger
from simulation.scheduler import MilestoneScheduler

_VISITED_THRESHOLD = 0.5

_TRANSPORT_CLASS_MAP = {
    "FoxMQMeshBus": "foxmq",
    "LocalPeerMeshBus": "udp",
    "VertexMeshBus": "vertex",
    "InMemoryMeshBus": "in-process",
}

def _resolve_transport(mesh: object) -> str:
    inner = getattr(mesh, "_bus", mesh)
    return _TRANSPORT_CLASS_MAP.get(type(inner).__name__, type(inner).__name__)
_DECAY_MIDPOINT = 0.5

if TYPE_CHECKING:
    from collections.abc import Callable

    from auction.voronoi import PartitionOwner

@dataclass(frozen=True, slots=True, kw_only=True)
class SimulationConfig(BaseSimulationConfig):

    drones: int = 5
    fail_drone: str | None = "drone_2"
    fail_at: int | None = 60
    seed: int = 7
    final_map_path: str = "final_map.json"
    packet_loss: float = 0.0
    jitter_ms: float = 0.0
    transport: str = "in-process"

@dataclass(slots=True)
class DroneReplica:

    certainty_map: CertaintyMap
    heartbeats: HeartbeatRegistry = field(default_factory=HeartbeatRegistry)

class EntropyHuntSimulation:

    def __init__(
        self,
        config: SimulationConfig,
        *,
        mesh_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.config = config
        self.now_ms = 0
        self.random = random.Random(config.seed)
        self.mesh = mesh_factory() if mesh_factory is not None else InMemoryMeshBus()
        self.mesh_mode = getattr(
            self.mesh,
            "active_mode",
            "real" if self.mesh.__class__.__name__ == "VertexMeshBus" else "stub",
        )
        self._proof_logger = ProofLogger(config.proofs_path, source_mode="stub")
        _raw_mesh = self.mesh
        if config.packet_loss > 0.0 or config.jitter_ms > 0.0:
            self.mesh = NetworkInjector(
                _raw_mesh,
                packet_loss=config.packet_loss,
                jitter_ms=config.jitter_ms,
                proof_logger=self._proof_logger,
            )
        self.proofs_path = self._proof_logger.proofs_path
        self.certainty_map = CertaintyMap(
            config.grid,
            initial_certainty=_VISITED_THRESHOLD,
            decay_rate=config.decay_rate,
            now_ms=self.now_ms,
        )
        self.drones = self._build_drones(config.drones, config.grid)
        self.peer_ids = [drone.drone_id for drone in self.drones]
        self.selector = ZoneSelector()
        self._resolver = DeterministicResolver(self.peer_ids, mesh=_raw_mesh, quorum_timeout_s=0.05)
        self.failure_injector = FailureInjector(
            FailurePlan(drone_id=config.fail_drone, fail_at_seconds=config.fail_at),
        )
        self.replicas = {
            drone.drone_id: DroneReplica(
                certainty_map=CertaintyMap(
                    config.grid,
                    initial_certainty=_VISITED_THRESHOLD,
                    decay_rate=config.decay_rate,
                    now_ms=self.now_ms,
                ),
            )
            for drone in self.drones
        }
        self.mesh_heartbeat = HeartbeatRegistry()
        scale_factor = min(1.0, config.duration / 180.0)
        self.scheduler = MilestoneScheduler(
            failure_at_s=config.fail_at or 60,
            contention_deadline_s=max(10, int(30 * scale_factor)),
            reclaim_force_at_s=max(20, int(75 * scale_factor)),
            target_unlock_at_s=max(30, int(90 * scale_factor)),
            target_force_at_s=max(40, int(110 * scale_factor)),
            survivor_deadline_s=max(50, int(150 * scale_factor)),
            contention_cell=None,
        )
        self.events: list[dict[str, Any]] = self._proof_logger.events
        self.dropouts = 0
        self.auctions = 0
        self.survivor_found = False
        self.survivor_receipts: set[str] = set()
        self.completed_cells: set[Coordinate] = set()
        self.split_progress: dict[tuple[Coordinate, str], float] = {}
        self.priority_release_queue: list[Coordinate] = []
        self.priority_target_queue: list[Coordinate] = []
        self._recovered_drones: set[str] = set()
        self._pending_bus_results: list[dict[str, Any]] = []
        self._subscribers = ["simulation", *self.peer_ids]
        for subscriber_id in self._subscribers:
            self.mesh.subscribe(subscriber_id, "swarm/#")

    def _build_drones(self, count: int, grid: int) -> list[DroneState]:
        drones: list[DroneState] = []
        peer_ids = [f"drone_{index + 1}" for index in range(count)]
        for index in range(count):
            drone_id = f"drone_{index + 1}"
            position = spread_starting_position(drone_id, peer_ids, grid)
            drones.append(DroneState(drone_id=drone_id, position=position))
        return drones

    def _seconds(self) -> int:
        return self.now_ms // 1000

    def _log(self, event_type: str, message: str, **data: object) -> None:
        self._proof_logger.log(self._seconds(), event_type, message, **data)

    def _publish(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        sender_id: str = "simulation",
    ) -> None:
        self.mesh.publish(topic, payload, timestamp_ms=self.now_ms, sender_id=sender_id)
        self.mesh_mode = getattr(self.mesh, "active_mode", self.mesh_mode)

    def _merge_certainty(
        self,
        certainty_map: CertaintyMap,
        coordinate: Coordinate,
        certainty: float,
        *,
        updated_by: str,
    ) -> None:
        existing = certainty_map.cell(coordinate)
        if self.now_ms > existing.last_updated_ms or (
            self.now_ms == existing.last_updated_ms and certainty > existing.certainty
        ):
            certainty_map.set_certainty(
                coordinate,
                certainty,
                updated_by=updated_by,
                now_ms=self.now_ms,
            )

    def _consume_mesh(self) -> None:
        for envelope in self.mesh.poll("simulation"):
            if envelope.topic.startswith("swarm/heartbeat/"):
                drone_id = str(envelope.payload["drone_id"])
                self.mesh_heartbeat.beat(drone_id, now_ms=envelope.timestamp_ms)
            elif envelope.topic == "swarm/certainty_map":
                coordinate = tuple(envelope.payload["cell"])
                self._merge_certainty(
                    self.certainty_map,
                    coordinate,
                    float(envelope.payload["certainty"]),
                    updated_by=str(envelope.payload["updated_by"]),
                )
            elif envelope.topic.startswith("swarm/consensus_result/"):
                self._pending_bus_results.append(dict(envelope.payload))
            elif envelope.topic.startswith("swarm/survivor_found_ack/"):
                self.survivor_receipts.add(str(envelope.payload["drone_id"]))

        for drone in self.drones:
            replica = self.replicas[drone.drone_id]
            for envelope in self.mesh.poll(drone.drone_id):
                if envelope.topic.startswith("swarm/heartbeat/"):
                    peer_id = str(envelope.payload["drone_id"])
                    replica.heartbeats.beat(peer_id, now_ms=envelope.timestamp_ms)
                elif envelope.topic == "swarm/certainty_map":
                    coordinate = tuple(envelope.payload["cell"])
                    self._merge_certainty(
                        replica.certainty_map,
                        coordinate,
                        float(envelope.payload["certainty"]),
                        updated_by=str(envelope.payload["updated_by"]),
                    )

    def _blocked_zones(self) -> set[Coordinate]:
        blocked: set[Coordinate] = set()
        if (
            self.scheduler.target_unlock_at_s > 0
            and self._seconds() < self.scheduler.target_unlock_at_s
            and self.config.target not in self.completed_cells
        ):
            blocked.add(self.config.target)
        return blocked

    def _claimed_zones(self) -> set[Coordinate]:
        return {
            drone.claimed_cell
            for drone in self.drones
            if drone.alive and drone.reachable and drone.claimed_cell is not None
        }

    def _active_split_keys(self) -> set[tuple[Coordinate, str]]:
        return {
            (drone.target_cell, drone.subzone)
            for drone in self.drones
            if (
                drone.alive
                and drone.reachable
                and drone.target_cell is not None
                and drone.subzone is not None
            )
        }

    def _decay_split_progress(self) -> None:
        active = self._active_split_keys()
        touched_cells: set[Coordinate] = set()
        for key, progress in list(self.split_progress.items()):
            if key in active:
                continue
            self.split_progress[key] = max(
                0.0,
                min(
                    1.0,
                    progress
                    + (
                        self.config.decay_rate
                        * self.config.tick_seconds
                        * (_DECAY_MIDPOINT - progress)
                    ),
                ),
            )
            touched_cells.add(key[0])
        for coordinate in touched_cells:
            self._update_split_cell(coordinate, updated_by="decay")

    def _update_split_cell(self, coordinate: Coordinate, *, updated_by: str) -> None:
        left = self.split_progress.get(
            (coordinate, "left"),
            self.certainty_map.cell(coordinate).certainty,
        )
        right = self.split_progress.get(
            (coordinate, "right"),
            self.certainty_map.cell(coordinate).certainty,
        )
        combined = (left + right) / 2.0
        self.certainty_map.set_certainty(
            coordinate,
            combined,
            updated_by=updated_by,
            now_ms=self.now_ms,
        )

    def _broadcast_survivor_receipts(self, *, source_drone_id: str, coordinate: Coordinate) -> None:
        for drone in self.drones:
            if not drone.alive or not drone.reachable or drone.drone_id == source_drone_id:
                continue
            self._publish(
                f"swarm/survivor_found_ack/{drone.drone_id}",
                {
                    "drone_id": drone.drone_id,
                    "source_drone_id": source_drone_id,
                    "cell": list(coordinate),
                },
                sender_id=drone.drone_id,
            )
            self._log(
                "survivor_ack",
                f"{drone.drone_id} received survivor event for {coordinate}",
                source_drone_id=source_drone_id,
            )

    def _create_claim(self, drone: DroneState, cell: Coordinate) -> ClaimRequest:
        claim = ClaimRequest(
            claim_id=f"{drone.drone_id}:{cell[0]}:{cell[1]}:{self.now_ms}",
            drone_id=drone.drone_id,
            cell=cell,
            position=drone.position,
            timestamp_ms=self.now_ms,
        )
        self._publish(
            "swarm/zone_claims",
            {
                "kind": "CLAIM",
                "claim_id": claim.claim_id,
                "drone_id": claim.drone_id,
                "cell": list(claim.cell),
                "position": list(claim.position),
                "timestamp_ms": claim.timestamp_ms,
            },
            sender_id=drone.drone_id,
        )
        drone.status = "computing"
        return claim

    def _log_round(self, round_result: ConsensusRoundResult) -> None:
        if len(round_result.assignments) > 1:
            self.auctions += 1
            self._log(
                "auction",
                f"auction resolved for {round_result.cell}",
                contest_id=round_result.contest_id,
                round_id=round_result.round_id,
                assignments=[asdict(assignment) for assignment in round_result.assignments],
                votes=[asdict(vote) for vote in round_result.votes],
            )
        self._log(
            "consensus",
            f"round {round_result.round_id} resolved "
            f"{round_result.cell} via {round_result.rationale}",
            contest_id=round_result.contest_id,
            round_id=round_result.round_id,
            assignments=[asdict(assignment) for assignment in round_result.assignments],
            votes=[asdict(vote) for vote in round_result.votes],
            vote_count=len(round_result.votes),
        )

    def _apply_assignment(self, assignment: ZoneAssignment, by_id: dict[str, DroneState]) -> None:
        drone = by_id[assignment.drone_id]
        if assignment.reason == "idle":
            drone.status = "idle"
            return
        drone.set_assignment(assignment.cell, subzone=assignment.subzone)
        drone.status = (
            "claim_won"
            if assignment.reason in {"winner", "split", "priority_reclaim", "priority_target"}
            else "claim_lost"
        )
        self._log(
            "claim",
            f"{drone.drone_id} assigned {assignment.cell}",
            reason=assignment.reason,
            subzone=assignment.subzone,
        )
        if (
            assignment.cell == self.scheduler.released_cell
            and self.scheduler.reclaimed_time_s is None
        ):
            self.scheduler.reclaimed_time_s = self._seconds()
            self._log(
                "zone_priority_reclaim",
                f"{drone.drone_id} reclaimed released zone {assignment.cell}",
                cell=list(assignment.cell),
                owner=drone.drone_id,
            )

    def _process_priority_release_queue(
        self,
        idle_drones: list[DroneState],
        by_id: dict[str, DroneState],
    ) -> list[DroneState]:
        if (
            self.priority_release_queue
            and not idle_drones
            and self.scheduler.release_time_s is not None
            and self._seconds() - self.scheduler.release_time_s >= 1
        ):
            release_cell = self.priority_release_queue[0]
            candidate = min(
                (
                    drone
                    for drone in self.drones
                    if drone.alive and drone.reachable and drone.drone_id != self.config.fail_drone
                ),
                key=lambda drone: (
                    abs(drone.position[0] - release_cell[0])
                    + abs(drone.position[1] - release_cell[1]),
                    drone.drone_id,
                ),
                default=None,
            )
            if candidate is not None:
                candidate.clear_assignment()
                idle_drones = [candidate]
        while self.priority_release_queue and idle_drones:
            cell = self.priority_release_queue.pop(0)
            drone = idle_drones.pop(0)
            self._create_claim(drone, cell)
            self._apply_assignment(
                ZoneAssignment(drone_id=drone.drone_id, cell=cell, reason="priority_reclaim"),
                by_id,
            )
        return idle_drones

    def _process_priority_target_queue(
        self,
        idle_drones: list[DroneState],
        by_id: dict[str, DroneState],
    ) -> list[DroneState]:
        while self.priority_target_queue and idle_drones:
            cell = self.priority_target_queue.pop(0)
            drone = idle_drones.pop(0)
            self._create_claim(drone, cell)
            self._apply_assignment(
                ZoneAssignment(drone_id=drone.drone_id, cell=cell, reason="priority_target"),
                by_id,
            )
        return idle_drones

    def _assign_idle_drones(self) -> None:
        by_id = {drone.drone_id: drone for drone in self.drones}
        idle_drones = [
            drone
            for drone in self.drones
            if drone.alive and drone.reachable and drone.target_cell is None
        ]

        if (
            self.scheduler.released_cell is not None
            and self.scheduler.reclaimed_time_s is None
            and self._seconds() >= self.scheduler.reclaim_force_at_s
            and self.scheduler.released_cell not in self.priority_release_queue
        ):
            self.priority_release_queue.insert(0, self.scheduler.released_cell)

        if (
            not self.survivor_found
            and self._seconds() >= self.scheduler.target_force_at_s
            and self.config.target not in self.completed_cells
            and all(
                drone.target_cell != self.config.target
                for drone in self.drones
                if drone.alive and drone.reachable
            )
            and self.config.target not in self.priority_target_queue
        ):
            self.scheduler.target_priority_armed = True
            self.priority_target_queue.append(self.config.target)

        idle_drones = self._process_priority_release_queue(idle_drones, by_id)
        idle_drones = self._process_priority_target_queue(idle_drones, by_id)
        if not idle_drones:
            return

        claimed = self._claimed_zones()
        blocked = self._blocked_zones()
        claims: list[ClaimRequest] = []
        reserved = set(claimed)
        share_initial_view = not self.scheduler.contention_complete

        for drone in idle_drones:
            selection = self.selector.select_next_zone(
                self.replicas[drone.drone_id].certainty_map,
                claimed_zones=claimed if share_initial_view else reserved,
                blocked_zones=blocked,
                current_position=drone.position,
                ignore_distance=share_initial_view,
            )
            if selection is None:
                drone.status = "idle"
                continue
            claim = self._create_claim(drone, selection.coordinate)
            claims.append(claim)
            drone.status = "claiming"
            if not share_initial_view:
                reserved.add(selection.coordinate)

        if not claims:
            return

        grouped: dict[Coordinate, list[ClaimRequest]] = {}
        for claim in claims:
            grouped.setdefault(claim.cell, []).append(claim)

        for cell in sorted(grouped):
            round_result = self._resolver.resolve_claims(
                grouped[cell],
                ResolveClaimsRequest(
                    certainty_map=self.certainty_map,
                    selector=self.selector,
                    claimed_zones=claimed,
                    now_ms=self.now_ms,
                    initiator_id=grouped[cell][0].drone_id,
                    per_peer_maps={
                        did: r.certainty_map for did, r in self.replicas.items()
                    },
                ),
            )
            self._log_round(round_result)
            if len(grouped[cell]) > 1:
                self.scheduler.contention_complete = True
            for assignment in round_result.assignments:
                self._apply_assignment(assignment, by_id)

    def _mark_drone_stale(self, drone: DroneState) -> None:
        if not drone.alive:
            return
        released_cell = drone.claimed_cell
        if released_cell is not None:
            release_round = self._resolver.confirm_release(
                drone_id=drone.drone_id,
                cell=released_cell,
                now_ms=self.now_ms,
            )
            self._publish(
                f"swarm/consensus_result/{release_round.contest_id}",
                {
                    "contest_id": release_round.contest_id,
                    "round_id": release_round.round_id,
                    "cell": list(release_round.cell),
                    "assignments": [],
                    "rationale": release_round.rationale,
                    "released_by": drone.drone_id,
                },
            )
            self.scheduler.released_cell = released_cell
            self.scheduler.release_time_s = self._seconds()
            if released_cell not in self.priority_release_queue:
                self.priority_release_queue.append(released_cell)
            self._log(
                "zone_release",
                f"released zone {released_cell} after {drone.drone_id} heartbeat timeout",
                cell=list(released_cell),
                released_by=drone.drone_id,
            )
        drone.mark_stale()
        dead_map = self.replicas[drone.drone_id].certainty_map
        for survivor in self.drones:
            if survivor.alive and survivor.drone_id != drone.drone_id:
                self.replicas[survivor.drone_id].certainty_map.merge_timestamped_from(dead_map)
        if released_cell is not None:
            self._publish(
                "swarm/zone_reclaim",
                {
                    "released_by": drone.drone_id,
                    "cell": list(released_cell),
                    "reason": "dropout_reallocation",
                },
            )
            self._log(
                "role_reallocation",
                f"broadcasting {released_cell} for re-claim after {drone.drone_id} dropout",
                cell=list(released_cell),
                released_by=drone.drone_id,
            )
        self._log(
            "heartbeat_timeout",
            f"{drone.drone_id} heartbeat timeout",
            drone_id=drone.drone_id,
        )
        self._log("stale", f"{drone.drone_id} marked stale", drone_id=drone.drone_id)

    def _export_snapshot(self) -> SnapshotExporter:
        return SnapshotExporter(self.config, self.certainty_map, self.drones)

    def _heartbeat_tick(self) -> None:
        for drone in self.drones:
            if drone.alive and drone.reachable:
                self._publish(
                    f"swarm/heartbeat/{drone.drone_id}",
                    {"drone_id": drone.drone_id, "position": list(drone.position)},
                    sender_id=drone.drone_id,
                )
        self._consume_mesh()

        online_observers = [drone for drone in self.drones if drone.alive and drone.reachable]
        quorum = max(1, len(online_observers) // 2 + 1)
        stale_votes: Counter[str] = Counter()
        for observer in online_observers:
            status = self.replicas[observer.drone_id].heartbeats.detect_stale(
                now_ms=self.now_ms,
                timeout_ms=self.config.stale_after_seconds * 1000,
            )
            for stale_id in status.stale:
                stale_votes[stale_id] += 1

        for drone in self.drones:
            if drone.alive and stale_votes.get(drone.drone_id, 0) >= quorum:
                self._mark_drone_stale(drone)

    def _inject_failure(self) -> None:
        event = self.failure_injector.maybe_trigger(self.drones, now_seconds=self._seconds())
        if event is None:
            return
        self.dropouts += 1
        drone = next(drone for drone in self.drones if drone.drone_id == event.drone_id)
        self.scheduler.failure_logged = True
        self._log(
            "node_failure",
            f"{drone.drone_id} node failure injected",
            drone_id=drone.drone_id,
        )
        self._log(
            "failure",
            (
                f"{drone.drone_id} dropped off-mesh; waiting "
                f"{self.config.stale_after_seconds}s for stale release"
            ),
            zone=list(drone.claimed_cell) if drone.claimed_cell is not None else None,
            mode=event.mode,
        )

    def _decay_maps(self) -> None:
        self.certainty_map.decay_all(seconds=self.config.tick_seconds, now_ms=self.now_ms)
        for replica in self.replicas.values():
            replica.certainty_map.decay_all(seconds=self.config.tick_seconds, now_ms=self.now_ms)
        self._decay_split_progress()

    def _move_and_search(self) -> None:
        for drone in self.drones:
            if not drone.alive or not drone.reachable:
                continue
            if drone.status in {"claim_won", "claim_lost"}:
                drone.status = "transiting" if drone.position != drone.target_cell else "searching"
            if drone.target_cell is None:
                drone.status = "idle"
                continue
            if drone.position != drone.target_cell:
                drone.step_towards_target()
                self._publish(
                    f"swarm/drone_state/{drone.drone_id}",
                    {
                        "drone_id": drone.drone_id,
                        "position": list(drone.position),
                        "target": list(drone.target_cell),
                        "status": drone.status,
                    },
                    sender_id=drone.drone_id,
                )
                continue

            drone.status = "searching"
            if drone.subzone is None:
                updated = self.replicas[drone.drone_id].certainty_map.update_cell(
                    drone.target_cell,
                    updated_by=drone.drone_id,
                    increment=self.config.search_increment,
                    now_ms=self.now_ms,
                )
                current_certainty = updated.certainty
            else:
                key = (drone.target_cell, drone.subzone)
                starting_progress = self.split_progress.get(
                    key,
                    self.certainty_map.cell(drone.target_cell).certainty,
                )
                self.split_progress[key] = min(
                    1.0,
                    starting_progress + self.config.search_increment,
                )
                self._update_split_cell(drone.target_cell, updated_by=drone.drone_id)
                current_certainty = self.certainty_map.cell(drone.target_cell).certainty
                updated = self.replicas[drone.drone_id].certainty_map.set_certainty(
                    drone.target_cell,
                    current_certainty,
                    updated_by=drone.drone_id,
                    now_ms=self.now_ms,
                )

            drone.searched_cells += 1
            self._publish(
                "swarm/certainty_map",
                {
                    "updated_by": drone.drone_id,
                    "cell": list(updated.coordinate),
                    "certainty": current_certainty,
                },
                sender_id=drone.drone_id,
            )

            if (
                drone.target_cell == self.config.target
                and self._seconds() >= self.scheduler.target_unlock_at_s
                and current_certainty >= self.config.completion_certainty
            ):
                self.survivor_found = True
                self._publish(
                    "swarm/survivor_found",
                    {
                        "cell": list(drone.target_cell),
                        "confidence": round(current_certainty, 3),
                        "drone_id": drone.drone_id,
                    },
                    sender_id=drone.drone_id,
                )
                self._log(
                    "survivor_found",
                    f"survivor found by {drone.drone_id} at {drone.target_cell}",
                    confidence=round(current_certainty, 3),
                )
                self._broadcast_survivor_receipts(
                    source_drone_id=drone.drone_id,
                    coordinate=drone.target_cell,
                )

            assignment_complete = (
                current_certainty >= self.config.completion_certainty
                if drone.subzone is None
                else self.split_progress[(drone.target_cell, drone.subzone)]
                >= self.config.completion_certainty
            )
            if assignment_complete:
                if current_certainty >= self.config.completion_certainty:
                    self.completed_cells.add(drone.target_cell)
                self._log(
                    "zone_complete",
                    f"{drone.drone_id} completed {drone.target_cell}",
                    certainty=round(current_certainty, 3),
                    subzone=drone.subzone,
                )
                drone.clear_assignment()

        self._consume_mesh()

    def initialise(self) -> None:
        if (
            isinstance(self.mesh, VertexMeshBus)
            and self.mesh.bridge is not None
            and self.mesh.bridge.proc is not None
            and self.mesh.bridge.proc.poll() is not None
        ):
            self.mesh.active_mode = "stub"
            self.mesh_mode = "stub"
        if self.scheduler.contention_cell is None:
            ranked = self.certainty_map.ranked_cells()
            self.scheduler.contention_cell = (
                ranked[0].coordinate
                if ranked
                else (min(5, self.config.grid - 1), min(5, self.config.grid - 1))
            )
        if self.mesh_mode == "real":
            self._log("mesh", "vertex p2p discovery complete", peers=len(self.drones))
            self._log("map", "foxmq certainty map initialised", grid=self.config.grid)
        else:
            self._log(
                "mesh",
                "in-process mesh bus initialised (InMemoryMeshBus)",
                peers=len(self.drones),
            )
            self._log(
                "map",
                f"certainty map initialised — "
                f"{self.config.grid}×{self.config.grid} grid, all H=1.00",
                grid=self.config.grid,
            )
        for i, drone in enumerate(self.drones):
            if i == 0:
                drone.role = "carrier"
            elif i % 3 == 0:
                drone.role = "relay"
            else:
                drone.role = "scout"
            self._log("mesh", f"{drone.drone_id} online as {drone.role}",
                      drone_id=drone.drone_id, role=drone.role)
        self._heartbeat_tick()
        for drone in self.drones:
            self._publish(
                "swarm/hello",
                {"type": "HELLO", "drone_id": drone.drone_id, "position": list(drone.position)},
                sender_id=drone.drone_id,
            )
        self._consume_mesh()
        self._log("peer_discovery", "swarm hello phase complete", peers=len(self.drones))
        self._assign_idle_drones()

    def _check_recovery(self) -> None:
        if self.config.fail_drone is None or self.config.fail_at is None:
            return
        for drone in self.drones:
            if (
                (not drone.reachable or not drone.alive)
                and drone.drone_id == self.config.fail_drone
                and self._seconds() >= self.config.fail_at + 20
                and drone.drone_id not in self._recovered_drones
            ):
                drone.revive(drone.position)
                self._recovered_drones.add(drone.drone_id)
                self._log(
                    "recovery",
                    f"{drone.drone_id} reconnected to mesh",
                    drone_id=drone.drone_id,
                    recovered_at=self._seconds(),
                )

    def tick(self) -> None:
        self.now_ms += self.config.tick_seconds * 1000
        self._inject_failure()
        self._check_recovery()
        self._heartbeat_tick()
        self._decay_maps()
        self._move_and_search()
        if self.survivor_found and self.config.stop_on_survivor:
            return
        self._assign_idle_drones()

    def run(self) -> dict[str, Any]:
        self.initialise()
        total_ticks = self.config.duration // self.config.tick_seconds
        for _ in range(total_ticks):
            self.tick()
            if self.survivor_found and self.config.stop_on_survivor:
                break
        self._consume_mesh()
        self._proof_logger.log(
            self._seconds(), "grid_coverage", "final coverage",
            coverage_pct=self._compute_coverage(),
        )
        summary = self.summary()
        self.save_final_map(Path(self.config.final_map_path))
        poc_path = Path(self.config.proofs_path).with_name("proof_of_coordination.json")
        self._proof_logger.close()
        self._proof_logger.finalize(
            poc_path, mesh_transport=_resolve_transport(self.mesh),
        )
        self.mesh.close()
        return summary

    def finalize(self) -> dict[str, Any]:
        self._proof_logger.log(
            self._seconds(), "grid_coverage", "final coverage",
            coverage_pct=self._compute_coverage(),
        )
        summary = self.summary()
        self.save_final_map(Path(self.config.final_map_path))
        poc_path = Path(self.config.proofs_path).with_name("proof_of_coordination.json")
        self._proof_logger.close()
        self._proof_logger.finalize(
            poc_path,
            mesh_transport=_resolve_transport(self.mesh),
        )
        return summary

    def get_state(self) -> dict[str, Any]:
        drones = []
        for drone in self.drones:
            current_entropy = shannon_entropy(self.certainty_map.cell(drone.position).certainty)
            drones.append(
                {
                    "id": drone.drone_id,
                    "alive": drone.alive,
                    "reachable": drone.reachable,
                    "position": list(drone.position),
                    "target": list(drone.target_cell) if drone.target_cell is not None else None,
                    "status": drone.status,
                    "current_entropy": current_entropy,
                },
            )
        return {
            "elapsed": self._seconds(),
            "coverage": round(
                self.certainty_map.coverage(threshold=self.config.completion_certainty) * 100,
                2,
            ),
            "coverage_percent": round(
                self.certainty_map.coverage(threshold=self.config.completion_certainty) * 100,
            ),
            "avg_entropy": self.certainty_map.average_entropy(),
            "average_entropy": self.certainty_map.average_entropy(),
            "auctions": self.auctions,
            "dropouts": self.dropouts,
            "consensus_rounds": self._resolver.round_id,
            "events": list(reversed(self.events[-8:])),
            "drones": drones,
            "grid": self.certainty_map.to_rows(),
            "target": list(self.config.target),
            "mesh": self.mesh_mode,
            "survivor_found": self.survivor_found,
        }

    def _visited_cells(self) -> set[Coordinate]:
        return {
            cell.coordinate for cell in self.certainty_map if cell.certainty > _VISITED_THRESHOLD
        }

    def _compute_coverage(self) -> float:
        total = self.config.grid * self.config.grid
        scanned = sum(1 for cell in self.certainty_map if cell.certainty > 0.5)
        return round(scanned / total, 4) if total else 0.0

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
            len(self._visited_cells()) / (self.config.grid * self.config.grid),
            3,
        )
        return {
            "duration_elapsed": self._seconds(),
            "coverage": completed_coverage,
            "coverage_completed": completed_coverage,
            "coverage_current": current_coverage,
            "coverage_visited": visited_coverage,
            "grid_coverage_pct": visited_coverage,
            "average_entropy": round(self.certainty_map.average_entropy(), 3),
            "consensus_rounds": self._resolver.round_id,
            "auctions": self.auctions,
            "dropouts": self.dropouts,
            "survivor_found": self.survivor_found,
            "survivor_receipts": len(self.survivor_receipts),
            "mesh_messages": self.mesh.count(),
            "target": list(self.config.target),
            "drones": [
                {
                    "id": drone.drone_id,
                    "alive": drone.alive,
                    "position": list(drone.position),
                    "target": list(drone.target_cell) if drone.target_cell is not None else None,
                    "claimed_cell": list(drone.claimed_cell)
                    if drone.claimed_cell is not None
                    else None,
                    "status": drone.status,
                    "searched_cells": drone.searched_cells,
                }
                for drone in self.drones
            ],
        }

    def partition_snapshot(self) -> tuple[PartitionOwner, ...]:
        return self._export_snapshot().partition_snapshot()

    def partition_boundary_cells(self) -> tuple[Coordinate, ...]:
        return self._export_snapshot().partition_boundary_cells()

    def _claimed_owner_map(self) -> dict[Coordinate, str]:
        return self._export_snapshot().claimed_owner_map()

    def save_final_map(self, path: Path) -> None:
        self._export_snapshot().save_final_map(path, self.summary(), self._proof_logger.events)
