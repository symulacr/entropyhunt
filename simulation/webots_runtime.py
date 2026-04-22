
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from simulation.runtime import PeerRuntime, PeerRuntimeConfig
from simulation.webots_controller import (
    basic_time_step,
    create_supervisor,
    get_node_by_def,
    node_position,
    set_node_position,
    step_robot,
)

if TYPE_CHECKING:
    from core.certainty import Coordinate
    from simulation.protocol import PeerEndpoint
    from simulation.webots_stubs import WebotsNode, WebotsSupervisor

@dataclass(frozen=True, slots=True)
class WebotsRuntimeConfig:

    peer_id: str = "drone_1"
    drone_def: str = "DRONE_1"
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
    search_increment: float = 0.12
    completion_certainty: float = 0.92
    decay_rate: float = 0.001
    stale_after_seconds: int = 3
    target_def: str = "TARGET"
    snapshot_path: str = "webots_world/webots_snapshot.json"
    final_map_path: str = "webots_world/webots_final_map.json"
    cell_size: float = 1.0
    altitude: float = 0.2
    origin_x: float | None = None
    origin_z: float | None = None
    max_steps: int = 0

class WebotsPeerRuntime:

    def __init__(
        self, config: WebotsRuntimeConfig, *, supervisor: WebotsSupervisor | None = None,
    ) -> None:
        self.config = config
        self.supervisor = supervisor or create_supervisor()
        self.time_step = basic_time_step(self.supervisor)
        self.step_count = 0
        _drone_node = get_node_by_def(self.supervisor, self.config.drone_def)
        if _drone_node is None:
            _msg = f"Webots DEF '{self.config.drone_def}' was not found"
            raise RuntimeError(_msg)
        self.drone_node: WebotsNode = _drone_node
        self.target_node = get_node_by_def(self.supervisor, self.config.target_def)
        self.target_cell = (
            self.world_to_cell(node_position(self.target_node))
            if self.target_node is not None
            else (self.config.grid // 2, self.config.grid // 2)
        )
        self.runtime = PeerRuntime(
            PeerRuntimeConfig(
                peer_id=self.config.peer_id,
                host=self.config.host,
                port=self.config.port,
                peers=self.config.peers,
                transport=self.config.transport,
                mqtt_host=self.config.mqtt_host,
                mqtt_port=self.config.mqtt_port,
                mqtt_username=self.config.mqtt_username,
                mqtt_password=self.config.mqtt_password,
                grid=self.config.grid,
                duration=self.config.duration,
                tick_seconds=self.config.tick_seconds,
                search_increment=self.config.search_increment,
                completion_certainty=self.config.completion_certainty,
                decay_rate=self.config.decay_rate,
                stale_after_seconds=self.config.stale_after_seconds,
                target=self.target_cell,
                final_map_path=self.config.final_map_path,
            ),
        )
        self.runtime.local_drone.position = self.world_to_cell(node_position(self.drone_node))

    def _origin_x(self) -> float:
        if self.config.origin_x is not None:
            return self.config.origin_x
        return -((self.config.grid - 1) * self.config.cell_size) / 2.0

    def _origin_z(self) -> float:
        if self.config.origin_z is not None:
            return self.config.origin_z
        return -((self.config.grid - 1) * self.config.cell_size) / 2.0

    def world_to_cell(self, position: tuple[float, float, float]) -> Coordinate:
        x = round((position[0] - self._origin_x()) / self.config.cell_size)
        y = round((position[2] - self._origin_z()) / self.config.cell_size)
        x = max(0, min(self.config.grid - 1, x))
        y = max(0, min(self.config.grid - 1, y))
        return (x, y)

    def cell_to_world(self, coordinate: Coordinate) -> tuple[float, float, float]:
        return (
            self._origin_x() + coordinate[0] * self.config.cell_size,
            self.config.altitude,
            self._origin_z() + coordinate[1] * self.config.cell_size,
        )

    def _node_snapshot(self, def_name: str) -> dict[str, object] | None:
        node = get_node_by_def(self.supervisor, def_name)
        if node is None:
            return None
        x, y, z = node_position(node)
        return {
            "def": def_name,
            "position": [x, y, z],
            "grid_cell": list(self.world_to_cell((x, y, z))),
        }

    def _sync_runtime_from_world(self) -> None:
        self.runtime.local_drone.position = self.world_to_cell(node_position(self.drone_node))

    def _drive_toward_target(self) -> None:
        target_cell = self.runtime.local_drone.target_cell
        if target_cell is None:
            return
        current = node_position(self.drone_node)
        desired = self.cell_to_world(target_cell)
        step = self.config.cell_size * 0.45

        def _advance(current_value: float, desired_value: float) -> float:
            delta = desired_value - current_value
            if abs(delta) <= step:
                return desired_value
            return current_value + step if delta > 0 else current_value - step

        next_position = (
            _advance(current[0], desired[0]),
            desired[1],
            _advance(current[2], desired[2]),
        )
        set_node_position(self.drone_node, next_position)

    def snapshot(self) -> dict[str, object]:
        drones = [
            snapshot
            for def_name in (
                self.config.drone_def,
                *(peer.peer_id.upper() for peer in self.config.peers if peer.peer_id),
            )
            if (snapshot := self._node_snapshot(def_name)) is not None
        ]
        target = self._node_snapshot(self.config.target_def)
        return {
            "time_step": self.time_step,
            "step_count": self.step_count,
            "drones": drones,
            "target": target,
            "world_mode": "webots-peer-runtime",
            "peer_summary": self.runtime.summary(),
            "events": self.runtime.events[-20:],
            "config": asdict(self.config),
        }

    def write_snapshot(self, path: str | Path | None = None) -> dict[str, object]:
        snapshot = self.snapshot()
        output_path = Path(path or self.config.snapshot_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(snapshot, indent=2) + "\n")
        return snapshot

    def step(self) -> int:
        result = step_robot(self.supervisor, self.time_step)
        if result == -1:
            return result
        self.step_count += 1
        self._sync_runtime_from_world()
        self.runtime.tick()
        self._drive_toward_target()
        self.write_snapshot()
        return result

    def run(self) -> int:
        self.runtime.bootstrap()
        while True:
            result = self.step()
            if result == -1:
                break
            if self.config.max_steps and self.step_count >= self.config.max_steps:
                break
        if self.config.final_map_path:
            self.runtime.save_final_map(Path(self.config.final_map_path))
        self.runtime.mesh.close()
        return 0

def run_default_supervisor() -> int:
    runtime = WebotsPeerRuntime(WebotsRuntimeConfig())
    return runtime.run()
