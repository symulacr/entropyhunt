from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
import random
from typing import Any

from core.bft import BftCoordinator
from core.certainty_map import CertaintyMap, Coordinate
from core.heartbeat import HeartbeatRegistry
from core.mesh import MeshBus
from core.zone_selector import ZoneSelector
from roles.claimer import ClaimCoordinator
from roles.searcher import DroneState


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


class EntropyHuntSimulation:
    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self.now_ms = 0
        self.random = random.Random(config.seed)
        self.mesh = MeshBus()
        self.heartbeat = HeartbeatRegistry()
        self.certainty_map = CertaintyMap(
            config.grid,
            initial_certainty=0.5,
            decay_rate=config.decay_rate,
            now_ms=self.now_ms,
        )
        self.drones = self._build_drones(config.drones, config.grid)
        peer_ids = [drone.drone_id for drone in self.drones]
        self.selector = ZoneSelector()
        self.bft = BftCoordinator(peer_ids)
        self.claims = ClaimCoordinator(mesh=self.mesh, selector=self.selector, bft=self.bft)
        self.events: list[dict[str, Any]] = []
        self.dropouts = 0
        self.auctions = 0
        self.survivor_found = False
        self.survivor_receipts: set[str] = set()
        self.completed_cells: set[Coordinate] = set()
        self.split_progress: dict[tuple[Coordinate, str], float] = {}

    def _build_drones(self, count: int, grid: int) -> list[DroneState]:
        positions = [
            (0, 0),
            (grid - 1, 0),
            (0, grid - 1),
            (grid - 1, grid - 1),
            (grid // 2, grid // 2),
        ]
        drones: list[DroneState] = []
        for index in range(count):
            position = positions[index] if index < len(positions) else (
                self.random.randrange(grid),
                self.random.randrange(grid),
            )
            drones.append(DroneState(drone_id=f"drone_{index + 1}", position=position))
        return drones

    def _log(self, event_type: str, message: str, **data: Any) -> None:
        payload = {"t": self.now_ms // 1000, "type": event_type, "message": message, **data}
        self.events.append(payload)

    def _claimed_zones(self) -> set[Coordinate]:
        return {
            drone.claimed_cell
            for drone in self.drones
            if drone.alive and drone.claimed_cell is not None
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
                        * (0.5 - progress)
                    ),
                ),
            )
            touched_cells.add(key[0])
        for coordinate in touched_cells:
            self._update_split_cell(coordinate, updated_by="decay")

    def _update_split_cell(self, coordinate: Coordinate, *, updated_by: str) -> None:
        left = self.split_progress.get((coordinate, "left"), self.certainty_map.cell(coordinate).certainty)
        right = self.split_progress.get((coordinate, "right"), self.certainty_map.cell(coordinate).certainty)
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
            self.survivor_receipts.add(drone.drone_id)
            self.mesh.publish(
                f"swarm/survivor_found_ack/{drone.drone_id}",
                {
                    "drone_id": drone.drone_id,
                    "source_drone_id": source_drone_id,
                    "cell": coordinate,
                },
                timestamp_ms=self.now_ms,
            )
            self._log(
                "survivor_ack",
                f"{drone.drone_id} received survivor event for {coordinate}",
                source_drone_id=source_drone_id,
            )

    def _assign_idle_drones(self) -> None:
        claim_candidates = self.claims.build_claims(
            self.drones,
            certainty_map=self.certainty_map,
            claimed_zones=self._claimed_zones(),
            now_ms=self.now_ms,
        )
        if not claim_candidates:
            return
        assignments, rounds = self.claims.resolve_batch(
            claim_candidates,
            certainty_map=self.certainty_map,
            claimed_zones=self._claimed_zones(),
            now_ms=self.now_ms,
        )
        self.auctions += sum(1 for round_result in rounds if len(round_result.assignments) > 1)
        for round_result in rounds:
            self._log(
                "bft",
                f"round {round_result.round_id} resolved {round_result.cell} via {round_result.rationale}",
                assignments=[asdict(assignment) for assignment in round_result.assignments],
            )
        by_id = {drone.drone_id: drone for drone in self.drones}
        for drone_id, assignment in assignments.items():
            drone = by_id[drone_id]
            if assignment.reason == "idle":
                drone.status = "idle"
                continue
            drone.set_assignment(assignment.cell, subzone=assignment.subzone)
            drone.status = "claim_won" if assignment.reason in {"winner", "split"} else "claim_lost"
            self._log(
                "claim",
                f"{drone_id} assigned {assignment.cell}",
                reason=assignment.reason,
                subzone=assignment.subzone,
            )

    def _heartbeat_tick(self) -> None:
        for drone in self.drones:
            if drone.alive and drone.reachable:
                self.heartbeat.beat(drone.drone_id, now_ms=self.now_ms)
                self.mesh.publish(
                    f"swarm/heartbeat/{drone.drone_id}",
                    {"drone_id": drone.drone_id, "position": drone.position},
                    timestamp_ms=self.now_ms,
                )
        status = self.heartbeat.detect_stale(
            now_ms=self.now_ms,
            timeout_ms=self.config.stale_after_seconds * 1000,
        )
        for drone in self.drones:
            if drone.drone_id in status.stale and drone.alive:
                released_cell = drone.claimed_cell
                if released_cell is not None:
                    release_round = self.bft.confirm_release(
                        drone_id=drone.drone_id,
                        cell=released_cell,
                    )
                    self.mesh.publish(
                        f"swarm/bft_round/{release_round.round_id}",
                        {
                            "cell": release_round.cell,
                            "assignments": [],
                            "rationale": release_round.rationale,
                            "released_by": drone.drone_id,
                        },
                        timestamp_ms=self.now_ms,
                    )
                    self._log(
                        "bft",
                        (
                            f"round {release_round.round_id} released {released_cell} "
                            f"after {drone.drone_id} heartbeat timeout"
                        ),
                    )
                drone.mark_stale()
                self._log("stale", f"{drone.drone_id} marked stale")

    def _inject_failure(self) -> None:
        if self.config.fail_drone is None or self.config.fail_at is None:
            return
        if self.now_ms // 1000 != self.config.fail_at:
            return
        for drone in self.drones:
            if drone.drone_id == self.config.fail_drone and drone.alive and drone.reachable:
                drone.reachable = False
                self.dropouts += 1
                self._log(
                    "failure",
                    (
                        f"{drone.drone_id} dropped off-mesh; waiting "
                        f"{self.config.stale_after_seconds}s for stale release"
                    ),
                    zone=drone.claimed_cell,
                )
                return

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
                self.mesh.publish(
                    f"swarm/drone_state/{drone.drone_id}",
                    {
                        "drone_id": drone.drone_id,
                        "position": drone.position,
                        "target": drone.target_cell,
                        "status": drone.status,
                    },
                    timestamp_ms=self.now_ms,
                )
                continue

            drone.status = "searching"
            if drone.subzone is None:
                updated = self.certainty_map.update_cell(
                    drone.target_cell,
                    updated_by=drone.drone_id,
                    increment=self.config.search_increment,
                    now_ms=self.now_ms,
                )
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
                updated = self.certainty_map.cell(drone.target_cell)
            drone.searched_cells += 1
            self.mesh.publish(
                "swarm/certainty_map",
                {"updated_by": drone.drone_id, "cell": updated.coordinate, "certainty": updated.certainty},
                timestamp_ms=self.now_ms,
            )
            if drone.target_cell == self.config.target and updated.certainty >= self.config.completion_certainty:
                self.survivor_found = True
                self.mesh.publish(
                    "swarm/survivor_found",
                    {
                        "cell": drone.target_cell,
                        "confidence": round(updated.certainty, 3),
                        "drone_id": drone.drone_id,
                    },
                    timestamp_ms=self.now_ms,
                )
                self._log(
                    "survivor",
                    f"survivor found by {drone.drone_id} at {drone.target_cell}",
                    confidence=round(updated.certainty, 3),
                )
                self._broadcast_survivor_receipts(
                    source_drone_id=drone.drone_id,
                    coordinate=drone.target_cell,
                )

            if drone.subzone is None:
                assignment_complete = updated.certainty >= self.config.completion_certainty
            else:
                assignment_complete = (
                    self.split_progress[(drone.target_cell, drone.subzone)]
                    >= self.config.completion_certainty
                )

            if assignment_complete:
                if updated.certainty >= self.config.completion_certainty:
                    self.completed_cells.add(drone.target_cell)
                self._log(
                    "zone_complete",
                    f"{drone.drone_id} completed {drone.target_cell}",
                    certainty=round(updated.certainty, 3),
                    subzone=drone.subzone,
                )
                drone.clear_assignment()

    def initialise(self) -> None:
        self._log("mesh", "vertex p2p discovery complete", peers=len(self.drones))
        self._log("map", "foxmq certainty map initialised", grid=self.config.grid)
        self._heartbeat_tick()
        self._assign_idle_drones()

    def tick(self) -> None:
        self.now_ms += self.config.tick_seconds * 1000
        self._inject_failure()
        self._heartbeat_tick()
        self.certainty_map.decay_all(seconds=self.config.tick_seconds, now_ms=self.now_ms)
        self._decay_split_progress()
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
        summary = self.summary()
        self.save_final_map(Path(self.config.final_map_path))
        return summary

    def summary(self) -> dict[str, Any]:
        return {
            "duration_elapsed": self.now_ms // 1000,
            "coverage": round(
                len(self.completed_cells) / (self.config.grid * self.config.grid),
                3,
            ),
            "average_entropy": round(self.certainty_map.average_entropy(), 3),
            "bft_rounds": self.bft._round_id,
            "auctions": self.auctions,
            "dropouts": self.dropouts,
            "survivor_found": self.survivor_found,
            "survivor_receipts": len(self.survivor_receipts),
            "mesh_messages": self.mesh.count(),
            "target": self.config.target,
            "drones": [
                {
                    "id": drone.drone_id,
                    "alive": drone.alive,
                    "position": drone.position,
                    "target": drone.target_cell,
                    "status": drone.status,
                    "searched_cells": drone.searched_cells,
                }
                for drone in self.drones
            ],
        }

    def save_final_map(self, path: Path) -> None:
        payload = {
            "summary": self.summary(),
            "events": self.events,
            "grid": self.certainty_map.to_rows(),
        }
        path.write_text(json.dumps(payload, indent=2) + "\n")
