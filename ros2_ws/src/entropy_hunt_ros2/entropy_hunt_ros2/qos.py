from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
except ModuleNotFoundError:
    DurabilityPolicy = HistoryPolicy = ReliabilityPolicy = None
    QoSProfile = None


@dataclass(frozen=True, slots=True)
class QoSDescriptor:
    name: str
    depth: int
    reliability: str
    durability: str
    history: str


def coordination_qos(depth: int = 10) -> Any:
    if QoSProfile is None:
        return QoSDescriptor(
            name="coordination",
            depth=depth,
            reliability="reliable",
            durability="volatile",
            history="keep_last",
        )
    return QoSProfile(
        depth=depth,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
        history=HistoryPolicy.KEEP_LAST,
    )


def telemetry_qos(depth: int = 10) -> Any:
    if QoSProfile is None:
        return QoSDescriptor(
            name="telemetry",
            depth=depth,
            reliability="best_effort",
            durability="volatile",
            history="keep_last",
        )
    return QoSProfile(
        depth=depth,
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
        history=HistoryPolicy.KEEP_LAST,
    )
