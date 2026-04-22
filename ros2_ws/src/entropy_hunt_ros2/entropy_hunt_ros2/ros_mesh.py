from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

try:
    from entropy_hunt_interfaces.msg import (
        Assignment,
        CertaintyUpdate,
        Claim,
        ConsensusRoundResult,
        DroneState,
        Heartbeat,
        RuntimeControl,
        SurvivorFound,
    )
except ModuleNotFoundError:
    Assignment = ConsensusRoundResult = CertaintyUpdate = Claim = DroneState = Heartbeat = (
        RuntimeControl
    ) = SurvivorFound = None

from . import topic_names
from .qos import coordination_qos, telemetry_qos


@dataclass(frozen=True, slots=True)
class TopicBinding:
    name: str
    message_type: Any
    qos: Any


@dataclass(frozen=True, slots=True)
class RosMeshBindings:
    heartbeat: TopicBinding
    drone_state: TopicBinding
    claims: TopicBinding
    consensus_result: TopicBinding
    certainty_update: TopicBinding
    survivor_found: TopicBinding
    runtime_control: TopicBinding


BINDINGS = RosMeshBindings(
    heartbeat=TopicBinding(topic_names.HEARTBEAT_TOPIC, Heartbeat, telemetry_qos(20)),
    drone_state=TopicBinding(topic_names.DRONE_STATE_TOPIC, DroneState, telemetry_qos(20)),
    claims=TopicBinding(topic_names.CLAIMS_TOPIC, Claim, coordination_qos(20)),
    consensus_result=TopicBinding(
        topic_names.CONSENSUS_RESULT_TOPIC,
        ConsensusRoundResult,
        coordination_qos(20),
    ),
    certainty_update=TopicBinding(
        topic_names.CERTAINTY_UPDATE_TOPIC,
        CertaintyUpdate,
        telemetry_qos(50),
    ),
    survivor_found=TopicBinding(
        topic_names.SURVIVOR_FOUND_TOPIC,
        SurvivorFound,
        coordination_qos(10),
    ),
    runtime_control=TopicBinding(
        topic_names.RUNTIME_CONTROL_TOPIC,
        RuntimeControl,
        coordination_qos(10),
    ),
)


def all_bindings() -> list[TopicBinding]:
    return [getattr(BINDINGS, field.name) for field in fields(RosMeshBindings)]


def ensure_ros_messages_available() -> None:
    if any(binding.message_type is None for binding in all_bindings()):
        raise RuntimeError(
            "ROS interfaces are not available. Build the ROS workspace "
            "with colcon and source install/setup.bash first.",
        )


def create_publishers(node: Any) -> dict[str, Any]:
    ensure_ros_messages_available()
    return {
        field.name: node.create_publisher(binding.message_type, binding.name, binding.qos)
        for field in fields(RosMeshBindings)
        for binding in [getattr(BINDINGS, field.name)]
    }


def create_subscription(node: Any, binding: TopicBinding, callback: Any) -> Any:
    ensure_ros_messages_available()
    return node.create_subscription(binding.message_type, binding.name, callback, binding.qos)


def create_heartbeat_message(
    *,
    drone_id: str,
    x: int,
    y: int,
    alive: bool,
    reachable: bool,
    timestamp_ms: int,
    altitude_m: float = 0.0,
    heading_deg: float = 0.0,
    battery_pct: float = 100.0,
    flight_mode: str = "UNKNOWN",
) -> Any:
    ensure_ros_messages_available()
    msg = Heartbeat()
    msg.drone_id = drone_id
    msg.x = x
    msg.y = y
    msg.alive = alive
    msg.reachable = reachable
    msg.timestamp_ms = timestamp_ms
    msg.altitude_m = float(altitude_m)
    msg.heading_deg = float(heading_deg)
    msg.battery_pct = float(battery_pct)
    msg.flight_mode = str(flight_mode)
    return msg


def create_drone_state_message(
    *,
    drone_id: str,
    x: int,
    y: int,
    tx: int,
    ty: int,
    status: str,
    alive: bool,
    reachable: bool,
    searched_cells: int,
    altitude_m: float = 0.0,
    heading_deg: float = 0.0,
    battery_pct: float = 100.0,
    flight_mode: str = "UNKNOWN",
) -> Any:
    ensure_ros_messages_available()
    msg = DroneState()
    msg.drone_id = drone_id
    msg.x = x
    msg.y = y
    msg.tx = tx
    msg.ty = ty
    msg.status = status
    msg.alive = alive
    msg.reachable = reachable
    msg.searched_cells = searched_cells
    msg.altitude_m = float(altitude_m)
    msg.heading_deg = float(heading_deg)
    msg.battery_pct = float(battery_pct)
    msg.flight_mode = str(flight_mode)
    return msg


def create_certainty_update_message(*, updated_by: str, x: int, y: int, certainty: float) -> Any:
    ensure_ros_messages_available()
    msg = CertaintyUpdate()
    msg.updated_by = updated_by
    msg.x = x
    msg.y = y
    msg.certainty = float(certainty)
    return msg


def create_survivor_found_message(*, drone_id: str, x: int, y: int, confidence: float) -> Any:
    ensure_ros_messages_available()
    msg = SurvivorFound()
    msg.drone_id = drone_id
    msg.x = x
    msg.y = y
    msg.confidence = float(confidence)
    return msg


def create_claim_message(*, claim_id: str, drone_id: str, x: int, y: int, timestamp_ms: int) -> Any:
    ensure_ros_messages_available()
    msg = Claim()
    msg.claim_id = claim_id
    msg.drone_id = drone_id
    msg.x = x
    msg.y = y
    msg.timestamp_ms = int(timestamp_ms)
    return msg


def create_assignment_message(
    *,
    drone_id: str,
    x: int,
    y: int,
    reason: str,
    subzone: str = "",
) -> Any:
    ensure_ros_messages_available()
    msg = Assignment()
    msg.drone_id = drone_id
    msg.x = x
    msg.y = y
    msg.reason = reason
    msg.subzone = subzone
    return msg


def create_consensus_result_message(
    *,
    round_id: int,
    contest_id: str,
    x: int,
    y: int,
    rationale: str,
    released_by: str = "",
    assignments: list[Any] | None = None,
) -> Any:
    ensure_ros_messages_available()
    msg = ConsensusRoundResult()
    msg.round_id = int(round_id)
    msg.contest_id = contest_id
    msg.x = x
    msg.y = y
    msg.rationale = rationale
    msg.released_by = released_by
    msg.assignments = assignments or []
    return msg


def create_runtime_control_message(
    *,
    tick_seconds: float,
    requested_drone_count: int,
    timestamp_ms: int,
) -> Any:
    ensure_ros_messages_available()
    msg = RuntimeControl()
    msg.tick_seconds = float(tick_seconds)
    msg.requested_drone_count = int(requested_drone_count)
    msg.timestamp_ms = int(timestamp_ms)
    return msg
