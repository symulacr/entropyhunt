from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DroneNodeParameters:
    peer_id: str
    grid: int
    target_x: int
    target_y: int
    tick_seconds: float
    fail_at: int


@dataclass(frozen=True, slots=True)
class OperatorNodeParameters:
    drone_count: int
    grid: int
    target_x: int
    target_y: int
    tick_seconds: float
    snapshot_path: str
    snapshot_host: str
    snapshot_port: int


def declare_drone_parameters(node: Any) -> None:
    node.declare_parameter("peer_id", "drone_1")
    node.declare_parameter("grid", 10)
    node.declare_parameter("target_x", 7)
    node.declare_parameter("target_y", 3)
    node.declare_parameter("tick_seconds", 1.0)
    node.declare_parameter("fail_at", -1)


def load_drone_parameters(node: Any) -> DroneNodeParameters:
    return DroneNodeParameters(
        peer_id=str(node.get_parameter("peer_id").value),
        grid=int(node.get_parameter("grid").value),
        target_x=int(node.get_parameter("target_x").value),
        target_y=int(node.get_parameter("target_y").value),
        tick_seconds=float(node.get_parameter("tick_seconds").value),
        fail_at=int(node.get_parameter("fail_at").value),
    )


def declare_operator_parameters(node: Any) -> None:
    node.declare_parameter("drone_count", 5)
    node.declare_parameter("grid", 10)
    node.declare_parameter("target_x", 7)
    node.declare_parameter("target_y", 3)
    node.declare_parameter("tick_seconds", 1.0)
    node.declare_parameter("snapshot_path", "")
    node.declare_parameter("snapshot_host", "127.0.0.1")
    node.declare_parameter("snapshot_port", 8776)


def load_operator_parameters(node: Any) -> OperatorNodeParameters:
    return OperatorNodeParameters(
        drone_count=int(node.get_parameter("drone_count").value),
        grid=int(node.get_parameter("grid").value),
        target_x=int(node.get_parameter("target_x").value),
        target_y=int(node.get_parameter("target_y").value),
        tick_seconds=float(node.get_parameter("tick_seconds").value),
        snapshot_path=str(node.get_parameter("snapshot_path").value),
        snapshot_host=str(node.get_parameter("snapshot_host").value),
        snapshot_port=int(node.get_parameter("snapshot_port").value),
    )
