from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
import random
from typing import Any, Callable

from auction.protocol import ClaimRequest, ZoneAssignment
from auction.voronoi import PartitionOwner, boundary_cells as voronoi_boundary_cells, partition_grid
from core.bft import BftCoordinator, BftRoundResult
from core.certainty_map import CertaintyMap, Coordinate, shannon_entropy
from core.heartbeat import HeartbeatRegistry
from core.mesh import MeshBus
from core.zone_selector import ZoneSelector
from failure.injector import FailureInjector, FailurePlan
from roles.searcher import DroneState
from simulation.webots_bridge import build_bridge_snapshot


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    drones: int = 5
    grid: int = 10
    duration: int = 180
    tick_seconds: int = 1
    search_increment: float = 0.05
    completion_certainty: float = 0.95
    decay_rate: float = 0.001
    stale_after_seconds: int = 3
    target: Coordinate = (7, 3)
    fail_drone: str | None = "drone_2"
    fail_at: int | None = 60
    stop_on_survivor: bool = False
    seed: int = 7
    final_map_path: str = "final_map.json"
    proofs_path: str = "proofs.jsonl"


@dataclass(slots=True)
class DroneReplica:
    certainty_map: CertaintyMap
    heartbeats: HeartbeatRegistry = field(default_factory=HeartbeatRegistry)


@dataclass(slots=True)
class MilestoneScheduler:
    contention_deadline_s: int = 30
    failure_at_s: int = 60
    reclaim_force_at_s: int = 75
    target_unlock_at_s: int = 90
    target_force_at_s: int = 110
    survivor_deadline_s: int = 150
    contention_cell: Coordinate = (5, 5)
    contention_complete: bool = False
    failure_logged: bool = False
    released_cell: Coordinate | None = None
    release_time_s: int | None = None
    reclaimed_time_s: int | None = None
    target_priority_armed: bool = False


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
        self.mesh = mesh_factory() if mesh_factory is not None else MeshBus()
        self.mesh_mode = getattr(
            self.mesh,
            "active_mode",
            "real" if self.mesh.__class__.__name__ == "VertexMeshBus" else "stub",
        )
        self.proofs_path = Path(config.proofs_path)
        self.proofs_path.write_text("")
        self.certainty_map = CertaintyMap(
            config.grid,
            initial_certainty=0.5,
            decay_rate=config.decay_rate,
            now_ms=self.now_ms,
        )
        self.drones = self._build_drones(config.drones, config.grid)
        self.peer_ids = [drone.drone_id for drone in self.drones]
        self.selector = ZoneSelector()
        self.bft = BftCoordinator(self.peer_ids, mesh=self.mesh)
        self.failure_injector = FailureInjector(
            FailurePlan(drone_id=config.fail_drone, fail_at_seconds=config.fail_at)
        )
        self.replicas = {
            drone.drone_id: DroneReplica(
                certainty_map=CertaintyMap(
                    config.grid,
                    initial_certainty=0.5,
                    decay_rate=config.decay_rate,
                    now_ms=self.now_ms,
                )
            )
            for drone in self.drones
        }
        self.mesh_heartbeat = HeartbeatRegistry()
        self.scheduler = MilestoneScheduler(
            failure_at_s=config.fail_at or 60,
            contention_cell=(min(5, config.grid - 1), min(5, config.grid - 1)),
        )
        self.events: list[dict[str, Any]] = []
        self.dropouts = 0
        self.auctions = 0
        self.survivor_found = False
        self.survivor_receipts: set[str] = set()
        self.completed_cells: set[Coordinate] = set()
        self.split_progress: dict[tuple[Coordinate, str], float] = {}
        self.priority_release_queue: list[Coordinate] = []
        self.priority_target_queue: list[Coordinate] = []
        self._pending_bus_results: list[dict[str, Any]] = []
        self._subscribers = ["simulation", *self.peer_ids]
        for subscriber_id in self._subscribers:
            self.mesh.subscribe(subscriber_id, "swarm/#")

    def _build_drones(self, count: int, grid: int) -> list[DroneState]:
        drones: list[DroneState] = []
        for index in range(count):
            position = (0, 0)
            drones.append(DroneState(drone_id=f"drone_{index + 1}", position=position))
        return drones

    def _seconds(self) -> int:
        return self.now_ms // 1000

    def _log(self, event_type: str, message: str, **data: Any) -> None:
        payload = {"t": self._seconds(), "type": event_type, "message": message, **data}
        self.events.append(payload)
        with self.proofs_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")

    def _publish(self, topic: str, payload: dict[str, Any], *, sender_id: str = "simulation") -> None:
        self.mesh.publish(topic, payload, timestamp_ms=self.now_ms, sender_id=sender_id)
        self.mesh_mode = getattr(self.mesh, "active_mode", self.mesh_mode)

    def _merge_certainty(self, certainty_map: CertaintyMap, coordinate: Coordinate, certainty: float, *, updated_by: str) -> None:
        existing = certainty_map.cell(coordinate).certainty
        certainty_map.set_certainty(
            coordinate,
            max(existing, certainty),
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
            elif envelope.topic.startswith("swarm/bft_result/"):
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
        if self._seconds() < self.scheduler.target_unlock_at_s and self.config.target not in self.completed_cells:
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
                    progress + (self.config.decay_rate * self.config.tick_seconds * (0.5 - progress)),
                ),
            )
            touched_cells.add(key[0])
        for coordinate in touched_cells:
            self._update_split_cell(coordinate, updated_by="decay")

    def _update_split_cell(self, coordinate: Coordinate, *, updated_by: str) -> None:
        left = self.split_progress.get((coordinate, "left"), self.certainty_map.cell(coordinate).certainty)
        right = self.split_progress.get((coordinate, "right"), self.certainty_map.cell(coordinate).certainty)
        combined = (left + right) / 2.0
        self.certainty_map.set_certainty(coordinate, combined, updated_by=updated_by, now_ms=self.now_ms)

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
        drone.status = "claiming"
        return claim

    def _log_round(self, round_result: BftRoundResult) -> None:
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
            "bft",
            f"round {round_result.round_id} resolved {round_result.cell} via {round_result.rationale}",
            contest_id=round_result.contest_id,
            assignments=[asdict(assignment) for assignment in round_result.assignments],
            vote_count=len(round_result.votes),
        )

    def _apply_assignment(self, assignment: ZoneAssignment, by_id: dict[str, DroneState]) -> None:
        drone = by_id[assignment.drone_id]
        if assignment.reason == "idle":
            drone.status = "idle"
            return
        drone.set_assignment(assignment.cell, subzone=assignment.subzone)
        drone.status = "claim_won" if assignment.reason in {"winner", "split", "priority_reclaim", "priority_target"} else "claim_lost"
        self._log(
            "claim",
            f"{drone.drone_id} assigned {assignment.cell}",
            reason=assignment.reason,
            subzone=assignment.subzone,
        )
        if assignment.cell == self.scheduler.released_cell and self.scheduler.reclaimed_time_s is None:
            self.scheduler.reclaimed_time_s = self._seconds()
            self._log(
                "zone_priority_reclaim",
                f"{drone.drone_id} reclaimed released zone {assignment.cell}",
                cell=list(assignment.cell),
                owner=drone.drone_id,
            )

    def _process_priority_release_queue(self, idle_drones: list[DroneState], by_id: dict[str, DroneState]) -> list[DroneState]:
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
                    abs(drone.position[0] - release_cell[0]) + abs(drone.position[1] - release_cell[1]),
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

    def _process_priority_target_queue(self, idle_drones: list[DroneState], by_id: dict[str, DroneState]) -> list[DroneState]:
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
            and all(drone.target_cell != self.config.target for drone in self.drones if drone.alive and drone.reachable)
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
            )
            if selection is None:
                drone.status = "idle"
                continue
            claim = self._create_claim(drone, selection.coordinate)
            claims.append(claim)
            if not share_initial_view:
                reserved.add(selection.coordinate)

        if not claims:
            return

        grouped: dict[Coordinate, list[ClaimRequest]] = {}
        for claim in claims:
            grouped.setdefault(claim.cell, []).append(claim)

        for cell in sorted(grouped):
            round_result = self.bft.resolve_claims(
                grouped[cell],
                certainty_map=self.certainty_map,
                selector=self.selector,
                claimed_zones=claimed,
                now_ms=self.now_ms,
                initiator_id=grouped[cell][0].drone_id,
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
            release_round = self.bft.confirm_release(drone_id=drone.drone_id, cell=released_cell)
            self._publish(
                f"swarm/bft_result/{release_round.contest_id}",
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
        self._log("heartbeat_timeout", f"{drone.drone_id} heartbeat timeout", drone_id=drone.drone_id)
        self._log("stale", f"{drone.drone_id} marked stale", drone_id=drone.drone_id)

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
                self.split_progress[key] = min(1.0, starting_progress + self.config.search_increment)
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
                self._broadcast_survivor_receipts(source_drone_id=drone.drone_id, coordinate=drone.target_cell)

            assignment_complete = (
                current_certainty >= self.config.completion_certainty
                if drone.subzone is None
                else self.split_progress[(drone.target_cell, drone.subzone)] >= self.config.completion_certainty
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
            hasattr(self.mesh, "bridge")
            and getattr(self.mesh, "bridge") is not None
            and getattr(self.mesh.bridge, "proc", None) is not None
            and self.mesh.bridge.proc.poll() is not None
        ):
            setattr(self.mesh, "active_mode", "stub")
            self.mesh_mode = "stub"
        if self.mesh_mode == "real":
            self._log("mesh", "vertex p2p discovery complete", peers=len(self.drones))
            self._log("map", "foxmq certainty map initialised", grid=self.config.grid)
        else:
            self._log("mesh", "in-process mesh bus initialised (InMemoryMeshBus)", peers=len(self.drones))
            self._log("map", f"certainty map initialised — {self.config.grid}×{self.config.grid} grid, all H=1.00", grid=self.config.grid)
        self._heartbeat_tick()
        self._assign_idle_drones()

    def tick(self) -> None:
        self.now_ms += self.config.tick_seconds * 1000
        self._inject_failure()
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
        summary = self.summary()
        self.save_final_map(Path(self.config.final_map_path))
        self.mesh.close()
        return summary

    def get_state(self) -> dict[str, Any]:
        drones = []
        for drone in self.drones:
            current_entropy = shannon_entropy(self.certainty_map.cell(drone.position).certainty)
            drones.append(
                {
                    "id": drone.drone_id,
                    "alive": drone.alive and drone.reachable,
                    "position": list(drone.position),
                    "target": list(drone.target_cell) if drone.target_cell is not None else None,
                    "status": drone.status,
                    "current_entropy": current_entropy,
                }
            )
        return {
            "elapsed": self._seconds(),
            "coverage": round(
                self.certainty_map.coverage(threshold=self.config.completion_certainty) * 100,
                2,
            ),
            "coverage_percent": int(round(self.certainty_map.coverage(threshold=self.config.completion_certainty) * 100)),
            "avg_entropy": self.certainty_map.average_entropy(),
            "average_entropy": self.certainty_map.average_entropy(),
            "auctions": self.auctions,
            "dropouts": self.dropouts,
            "bft_rounds": self.bft._round_id,
            "events": list(reversed(self.events[-8:])),
            "drones": drones,
            "grid": self.certainty_map.to_rows(),
            "target": list(self.config.target),
            "mesh": self.mesh_mode,
            "survivor_found": self.survivor_found,
        }

    def summary(self) -> dict[str, Any]:
        current_coverage = round(
            self.certainty_map.coverage(threshold=self.config.completion_certainty),
            3,
        )
        completed_coverage = round(len(self.completed_cells) / (self.config.grid * self.config.grid), 3)
        return {
            "duration_elapsed": self._seconds(),
            "coverage": completed_coverage,
            "coverage_completed": completed_coverage,
            "coverage_current": current_coverage,
            "average_entropy": round(self.certainty_map.average_entropy(), 3),
            "bft_rounds": self.bft._round_id,
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
                    "claimed_cell": list(drone.claimed_cell) if drone.claimed_cell is not None else None,
                    "status": drone.status,
                    "searched_cells": drone.searched_cells,
                }
                for drone in self.drones
            ],
        }

    def partition_snapshot(self) -> tuple[PartitionOwner, ...]:
        return partition_grid(
            size=self.config.grid,
            drone_positions={
                drone.drone_id: drone.position
                for drone in self.drones
                if drone.alive and drone.reachable
            },
        )

    def partition_boundary_cells(self) -> tuple[Coordinate, ...]:
        return voronoi_boundary_cells(self.partition_snapshot(), size=self.config.grid)

    def _claimed_owner_map(self) -> dict[Coordinate, str]:
        return {
            drone.claimed_cell: drone.drone_id
            for drone in self.drones
            if drone.alive and drone.reachable and drone.claimed_cell is not None
        }

    def save_final_map(self, path: Path) -> None:
        partitions = self.partition_snapshot()
        summary = self.summary()
        claimed_owner_map = self._claimed_owner_map()
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
            "config": asdict(self.config),
            "events": self.events,
            "grid": self.certainty_map.to_rows(claimed_owner_map),
            "partitions": [
                {"drone_id": partition.drone_id, "cells": list(partition.cells)}
                for partition in partitions
            ],
            "partition_boundaries": list(self.partition_boundary_cells()),
            "bridge_snapshot": build_bridge_snapshot(self.drones, tick_seconds=self.config.tick_seconds),
        }
        path.write_text(json.dumps(payload, indent=2) + "\n")
