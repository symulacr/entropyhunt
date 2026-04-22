
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.certainty import CellPayload, CertaintyMap, Coordinate, GridPayload
from roles.drone import DroneState
from simulation.protocol import (
    DroneStatePayload,
    drone_state_topic,
    heartbeat_topic,
    make_certainty_payload,
    make_drone_state_payload,
    make_heartbeat_payload,
    parse_certainty_payload,
    parse_drone_state_payload,
    parse_survivor_payload,
    survivor_ack_topic,
)

_VISITED_THRESHOLD = 0.5
_PEER_ID_PARTS_COUNT = 2

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from core.heartbeat import HeartbeatRegistry
    from core.mesh import MeshBusProtocol, MeshEnvelope
    from simulation.peer_config import PeerRuntimeConfig

class PeerMeshHandler:

    def __init__(
        self,
        *,
        config: PeerRuntimeConfig,
        mesh: MeshBusProtocol,
        local_drone: DroneState,
        local_map: CertaintyMap,
        peer_maps: dict[str, CertaintyMap],
        heartbeat: HeartbeatRegistry,
        peer_drones: dict[str, DroneState],
    ) -> None:
        self.config = config
        self.mesh = mesh
        self.local_drone = local_drone
        self.local_map = local_map
        self.peer_maps = peer_maps
        self.heartbeat = heartbeat
        self.peer_drones = peer_drones

        self.completed_cells: set[Coordinate] = set()
        self.visited_cells: set[Coordinate] = set()
        self.survivor_found: bool = False
        self.survivor_receipts: set[str] = set()
        self._peer_maps_dirty: bool = True
        self._stale_since_ms: dict[str, int] = {}
        self._last_snapshot_rows: GridPayload | None = None

    def ensure_peer(self, drone_id: str, *, position: Coordinate | None = None) -> DroneState:
        if drone_id not in self.peer_drones:
            self.peer_drones[drone_id] = DroneState(
                drone_id=drone_id,
                position=position or (0, 0),
            )
        elif position is not None:
            self.peer_drones[drone_id].position = position
        return self.peer_drones[drone_id]

    def known_peer_ids(self) -> list[str]:
        return sorted(self.peer_drones)

    @staticmethod
    def numeric_sort_key(peer_id: str) -> tuple[int, str]:
        parts = peer_id.rsplit("_", 1)
        if len(parts) == _PEER_ID_PARTS_COUNT and parts[1].isdigit():
            return (int(parts[1]), parts[0])
        return (0, peer_id)

    def _active_drones(self) -> Iterator[DroneState]:
        for drone in self.peer_drones.values():
            if drone.alive and drone.reachable:
                yield drone

    def claimed_zones(self) -> set[Coordinate]:
        return {
            drone.claimed_cell for drone in self._active_drones() if drone.claimed_cell is not None
        }

    def claimed_owner_map(self) -> dict[Coordinate, str]:
        return {
            drone.claimed_cell: drone.drone_id
            for drone in self._active_drones()
            if drone.claimed_cell is not None
        }

    def mark_stale_since(self, drone_id: str, now_ms: int) -> None:
        self._stale_since_ms[drone_id] = now_ms

    def ensure_peer_map(self, drone_id: str, now_ms: int) -> CertaintyMap:
        peer_map = self.peer_maps.get(drone_id)
        if peer_map is None:
            peer_map = CertaintyMap(
                self.config.grid,
                initial_certainty=_VISITED_THRESHOLD,
                decay_rate=self.config.decay_rate,
                now_ms=now_ms,
            )
            self.peer_maps[drone_id] = peer_map
        return peer_map

    def recompute_merged_map(
        self,
        merged_map: CertaintyMap,
        *,
        force: bool = False,
    ) -> CertaintyMap | None:
        if not force and not self._peer_maps_dirty:
            return None
        merged_map.reset_from(self.local_map)
        for peer_map in self.peer_maps.values():
            merged_map.merge_timestamped_from(peer_map)
        self._peer_maps_dirty = False
        return merged_map

    @property
    def needs_recompute(self) -> bool:
        return self._peer_maps_dirty

    def mark_peer_maps_dirty(self) -> None:
        self._peer_maps_dirty = True

    def update_visited_completed(self, peer_map: CertaintyMap) -> None:
        for cell in peer_map:
            if cell.certainty > _VISITED_THRESHOLD:
                self.visited_cells.add(cell.coordinate)
            if cell.certainty >= self.config.completion_certainty:
                self.completed_cells.add(cell.coordinate)

    def publish_heartbeat(self, now_ms: int, peer_status: str = "HEALTHY") -> None:
        if not self.local_drone.alive:
            return
        self.heartbeat.beat(self.local_drone.drone_id, now_ms=now_ms)
        self.mesh.publish(
            heartbeat_topic(self.local_drone.drone_id),
            make_heartbeat_payload(
                drone_id=self.local_drone.drone_id,
                position=self.local_drone.position,
                peer_status=peer_status,
            ),
            timestamp_ms=now_ms,
            sender_id=self.config.peer_id,
        )

    def publish_state(self, now_ms: int) -> None:
        self.mesh.publish(
            drone_state_topic(self.local_drone.drone_id),
            make_drone_state_payload(
                DroneStatePayload(
                    drone_id=self.local_drone.drone_id,
                    position=self.local_drone.position,
                    target=self.local_drone.target_cell,
                    status=self.local_drone.status,
                    alive=self.local_drone.alive,
                    reachable=self.local_drone.reachable,
                    claimed_cell=self.local_drone.claimed_cell,
                    searched_cells=self.local_drone.searched_cells,
                ),
            ),
            timestamp_ms=now_ms,
            sender_id=self.config.peer_id,
        )

    def publish_local_map_snapshot(self, now_ms: int) -> None:
        if self._last_snapshot_rows is None:
            rows = self.local_map.to_rows()
            self._last_snapshot_rows = rows
            self.mesh.publish(
                f"swarm/certainty_map/{self.config.peer_id}",
                {
                    "drone_id": self.config.peer_id,
                    "grid": rows,
                },
                timestamp_ms=now_ms,
                sender_id=self.config.peer_id,
            )
            return
        current_rows = self.local_map.to_rows()
        delta_cells: list[CellPayload] = []
        last_rows = self._last_snapshot_rows
        for _y, (current_row, last_row) in enumerate(zip(current_rows, last_rows, strict=True)):
            for _x, (current_cell, last_cell) in enumerate(zip(current_row, last_row, strict=True)):
                if current_cell.get("certainty") != last_cell.get("certainty") or current_cell.get(
                    "last_updated_ms",
                ) != last_cell.get("last_updated_ms"):
                    delta_cells.append(current_cell)
        self._last_snapshot_rows = current_rows
        if delta_cells:
            self.mesh.publish(
                f"swarm/certainty_map/{self.config.peer_id}",
                {
                    "drone_id": self.config.peer_id,
                    "grid_delta": delta_cells,
                },
                timestamp_ms=now_ms,
                sender_id=self.config.peer_id,
            )

    def publish_certainty_delta(
        self,
        coordinate: Coordinate,
        certainty: float,
        updated_by: str,
        now_ms: int,
    ) -> None:
        self.mesh.publish(
            "swarm/certainty_map",
            make_certainty_payload(
                updated_by=updated_by,
                cell=coordinate,
                certainty=certainty,
            ),
            timestamp_ms=now_ms,
            sender_id=self.config.peer_id,
        )

    def publish_survivor_ack(self, source_drone_id: str, cell: Coordinate, now_ms: int) -> None:
        self.mesh.publish(
            survivor_ack_topic(self.config.peer_id),
            {
                "drone_id": self.config.peer_id,
                "source_drone_id": source_drone_id,
                "cell": list(cell),
            },
            timestamp_ms=now_ms,
            sender_id=self.config.peer_id,
        )

    def handle_heartbeat(self, envelope: MeshEnvelope, log_fn: Callable[..., None]) -> None:
        payload = envelope.payload
        drone_id = str(payload["drone_id"])
        position = (int(payload["position"][0]), int(payload["position"][1]))
        peer = self.ensure_peer(drone_id, position=position)
        was_stale = not peer.reachable or not peer.alive or drone_id in self._stale_since_ms
        peer.alive = True
        peer.reachable = True
        self.heartbeat.beat(drone_id, now_ms=envelope.timestamp_ms)
        if was_stale:
            self._stale_since_ms.pop(drone_id, None)
            log_fn("peer_recovered", f"{drone_id} resumed heartbeating", drone_id=drone_id)

    def handle_drone_state(self, envelope: MeshEnvelope) -> None:
        payload = parse_drone_state_payload(envelope.payload)
        peer = self.ensure_peer(payload.drone_id, position=payload.position)
        peer.position = payload.position
        peer.target_cell = payload.target
        peer.claimed_cell = payload.claimed_cell
        peer.status = payload.status
        peer.alive = payload.alive
        peer.reachable = payload.reachable
        peer.searched_cells = payload.searched_cells

    def handle_certainty_update(self, envelope: MeshEnvelope, now_ms: int) -> None:
        if (
            envelope.topic.startswith("swarm/certainty_map/")
            and envelope.payload.get("grid") is not None
        ):
            drone_id = str(envelope.payload.get("peer_id", envelope.sender_id))
            peer_map = self.ensure_peer_map(drone_id, now_ms)
            peer_map.merge_rows_timestamped(
                envelope.payload["grid"],
                now_ms=envelope.timestamp_ms,
                updated_by=drone_id,
            )
            self.update_visited_completed(peer_map)
            self._peer_maps_dirty = True
            return

        if (
            envelope.topic.startswith("swarm/certainty_map/")
            and envelope.payload.get("grid_delta") is not None
        ):
            drone_id = str(envelope.payload.get("peer_id", envelope.sender_id))
            peer_map = self.ensure_peer_map(drone_id, now_ms)
            delta_cells = envelope.payload["grid_delta"]
            for cell_payload in delta_cells:
                coordinate = (int(cell_payload["x"]), int(cell_payload["y"]))
                incoming_certainty = float(cell_payload.get("certainty", _VISITED_THRESHOLD))
                incoming_ts = int(cell_payload.get("last_updated_ms", envelope.timestamp_ms))
                current = peer_map.cell(coordinate)
                if incoming_ts > current.last_updated_ms or (
                    incoming_ts == current.last_updated_ms
                    and incoming_certainty > current.certainty
                ):
                    peer_map.set_certainty(
                        coordinate,
                        incoming_certainty,
                        updated_by=drone_id,
                        now_ms=incoming_ts,
                    )
            self.update_visited_completed(peer_map)
            self._peer_maps_dirty = True
            return

        payload = parse_certainty_payload(envelope.payload)
        target_map = (
            self.local_map
            if payload.updated_by == self.config.peer_id
            else self.ensure_peer_map(payload.updated_by, now_ms)
        )
        cell_state = target_map.cell(payload.cell)
        if envelope.timestamp_ms > cell_state.last_updated_ms or (
            envelope.timestamp_ms == cell_state.last_updated_ms
            and payload.certainty > cell_state.certainty
        ):
            target_map.set_certainty(
                payload.cell,
                payload.certainty,
                updated_by=payload.updated_by,
                now_ms=envelope.timestamp_ms,
            )
        if payload.certainty > _VISITED_THRESHOLD:
            self.visited_cells.add(payload.cell)
        if payload.certainty >= self.config.completion_certainty:
            self.completed_cells.add(payload.cell)
        self._peer_maps_dirty = True

    def handle_survivor(
        self, envelope: MeshEnvelope, now_ms: int, log_fn: Callable[..., None],
    ) -> None:
        payload = parse_survivor_payload(envelope.payload)
        self.survivor_found = True
        log_fn("survivor", f"survivor found by {payload.drone_id} at {payload.cell}")
        if payload.drone_id != self.config.peer_id:
            self.publish_survivor_ack(payload.drone_id, payload.cell, now_ms)

    def handle_survivor_ack(self, envelope: MeshEnvelope) -> None:
        drone_id = str(envelope.payload["drone_id"])
        self.survivor_receipts.add(drone_id)

    def handle_rejoin(self, envelope: MeshEnvelope, log_fn: Callable[..., None]) -> None:
        payload = envelope.payload
        drone_id = str(payload["drone_id"])
        peer = self.ensure_peer(drone_id)
        peer.alive = True
        peer.reachable = True
        self.heartbeat.beat(drone_id, now_ms=envelope.timestamp_ms)
        log_fn("peer_recovered", f"{drone_id} rejoined mesh", drone_id=drone_id)

    def process_incoming_messages(
        self,
        now_ms: int,
        log_fn: Callable[..., None],
        claim_fn: Callable[[MeshEnvelope], None],
        round_fn: Callable[[MeshEnvelope], None],
    ) -> bool:
        certainty_changed = False
        for envelope in self.mesh.poll(subscriber_id=self.config.peer_id):
            if envelope.sender_id == self.config.peer_id:
                continue
            topic = envelope.topic
            if topic.startswith("swarm/heartbeat/"):
                self.handle_heartbeat(envelope, log_fn)
            elif topic.startswith("swarm/drone_state/"):
                self.handle_drone_state(envelope)
            elif topic == "swarm/zone_claims":
                claim_fn(envelope)
            elif topic.startswith("swarm/consensus_result/"):
                round_fn(envelope)
            elif topic.startswith("swarm/certainty_map"):
                self.handle_certainty_update(envelope, now_ms)
                certainty_changed = True
            elif topic == "swarm/survivor_found":
                self.handle_survivor(envelope, now_ms, log_fn)
            elif topic.startswith("swarm/survivor_found_ack/"):
                self.handle_survivor_ack(envelope)
            elif topic.startswith("swarm/rejoin/"):
                self.handle_rejoin(envelope, log_fn)
        return certainty_changed
