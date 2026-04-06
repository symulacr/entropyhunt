from __future__ import annotations

from typing import Any

try:
    import rclpy
    from rclpy.node import Node
except ModuleNotFoundError:
    rclpy = None
    Node = None

from .operator_state import OperatorState
from .parameters import declare_operator_parameters, load_operator_parameters
from .ros_mesh import BINDINGS, create_runtime_control_message, create_subscription, ensure_ros_messages_available
from .operator_server import OperatorSnapshotServer, write_snapshot_file
from .snapshot_builder import (
    AssignmentPayload,
    apply_bft_result,
    apply_certainty_update,
    apply_claim,
    apply_drone_state,
    apply_heartbeat,
    apply_survivor_found,
    build_snapshot,
)


OperatorNode: type[Any]


if Node is not None:
    class _OperatorNodeImpl(Node):
        def __init__(self) -> None:
            super().__init__("entropy_hunt_operator")
            declare_operator_parameters(self)
            self.params = load_operator_parameters(self)
            self.state = OperatorState.create(drone_count=self.params.drone_count, grid_size=self.params.grid)
            self._elapsed_seconds = 0
            self._control_tick_seconds = float(self.params.tick_seconds)
            self._requested_drone_count = int(self.params.drone_count)
            ensure_ros_messages_available()
            self._mesh_publishers = {
                "runtime_control": self.create_publisher(BINDINGS.runtime_control.message_type, BINDINGS.runtime_control.name, BINDINGS.runtime_control.qos),
            }
            self._subs = [
                create_subscription(self, BINDINGS.heartbeat, self._on_heartbeat),
                create_subscription(self, BINDINGS.drone_state, self._on_drone_state),
                create_subscription(self, BINDINGS.claims, self._on_claim),
                create_subscription(self, BINDINGS.bft_result, self._on_bft_result),
                create_subscription(self, BINDINGS.certainty_update, self._on_certainty_update),
                create_subscription(self, BINDINGS.survivor_found, self._on_survivor_found),
            ]
            self._report_timer = self.create_timer(2.0, self._report)
            self._server = None
            if self.params.snapshot_path:
                self._server = OperatorSnapshotServer(
                    self.params.snapshot_host,
                    self.params.snapshot_port,
                    self._build_snapshot,
                    self._build_control_payload,
                    self._apply_control_payload,
                )
                self._server.start()
            self.get_logger().info(
                f"Operator node listening to ROS swarm topics for {self.params.drone_count} drones"
            )

        def _on_heartbeat(self, message: Any) -> None:
            apply_heartbeat(
                self.state,
                drone_id=str(message.drone_id),
                timestamp_ms=int(message.timestamp_ms),
                alive=bool(message.alive),
                reachable=bool(message.reachable),
            )

        def _on_drone_state(self, message: Any) -> None:
            apply_drone_state(
                self.state,
                drone_id=str(message.drone_id),
                x=int(message.x),
                y=int(message.y),
                tx=int(message.tx),
                ty=int(message.ty),
                status=str(message.status),
                alive=bool(message.alive),
                reachable=bool(message.reachable),
                searched_cells=int(message.searched_cells),
            )

        def _on_claim(self, message: Any) -> None:
            apply_claim(
                self.state,
                claim_id=str(message.claim_id),
                drone_id=str(message.drone_id),
                x=int(message.x),
                y=int(message.y),
                timestamp_ms=int(message.timestamp_ms),
            )

        def _on_bft_result(self, message: Any) -> None:
            assignments: list[AssignmentPayload] = [
                {
                    "drone_id": str(assignment.drone_id),
                    "x": int(assignment.x),
                    "y": int(assignment.y),
                    "reason": str(assignment.reason),
                }
                for assignment in getattr(message, "assignments", [])
            ]
            apply_bft_result(
                self.state,
                contest_id=str(message.contest_id),
                x=int(message.x),
                y=int(message.y),
                assignments=assignments,
                rationale=str(message.rationale),
                timestamp_ms=self.get_clock().now().nanoseconds // 1_000_000,
            )

        def _on_certainty_update(self, message: Any) -> None:
            apply_certainty_update(
                self.state,
                x=int(message.x),
                y=int(message.y),
                certainty=float(message.certainty),
            )

        def _on_survivor_found(self, message: Any) -> None:
            apply_survivor_found(
                self.state,
                drone_id=str(message.drone_id),
                x=int(message.x),
                y=int(message.y),
                confidence=float(message.confidence),
                timestamp_ms=self.get_clock().now().nanoseconds // 1_000_000,
            )

        def _build_snapshot(self) -> dict[str, Any]:
            snapshot = build_snapshot(
                self.state,
                source_mode="live",
                mesh_mode="ros2",
                elapsed_seconds=self._elapsed_seconds,
            )
            snapshot["config"]["target"] = {"x": self.params.target_x, "y": self.params.target_y}
            snapshot["config"]["snapshot_url"] = f"http://{self.params.snapshot_host}:{self.params.snapshot_port}/snapshot.json"
            snapshot["config"]["tick_seconds"] = round(self._control_tick_seconds, 3)
            snapshot["config"]["requested_drone_count"] = self._requested_drone_count
            snapshot["config"]["control_url"] = "/control"
            snapshot["config"]["control_capabilities"] = self._build_control_payload()["control_capabilities"]
            return snapshot

        def _build_control_payload(self) -> dict[str, Any]:
            return {
                "tick_seconds": round(self._control_tick_seconds, 3),
                "requested_drone_count": self._requested_drone_count,
                "control_capabilities": {
                    "tick_seconds": "live",
                    "tick_delay_seconds": "unavailable",
                    "requested_drone_count": "next_run",
                },
                "status": "writable",
            }

        def _apply_control_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
            next_tick = payload.get("tick_seconds")
            next_count = payload.get("requested_drone_count")
            changed = False
            if isinstance(next_tick, (int, float)) and float(next_tick) > 0:
                normalized_tick = round(float(next_tick), 3)
                if normalized_tick != self._control_tick_seconds:
                    self._control_tick_seconds = normalized_tick
                    changed = True
            if isinstance(next_count, int) and next_count > 0 and next_count != self._requested_drone_count:
                self._requested_drone_count = next_count
                changed = True
            if changed:
                self._mesh_publishers["runtime_control"].publish(
                    create_runtime_control_message(
                        tick_seconds=float(self._control_tick_seconds),
                        requested_drone_count=int(self._requested_drone_count),
                        timestamp_ms=int(self.get_clock().now().nanoseconds // 1_000_000),
                    )
                )
                self.get_logger().info(
                    f"Operator control updated: tick={self._control_tick_seconds}s requested_drones={self._requested_drone_count}"
                )
            return self._build_control_payload()

        def _report(self) -> None:
            self._elapsed_seconds += 2
            snapshot = self._build_snapshot()
            self.get_logger().info(
                f"Operator snapshot: drones={len(self.state.drones)}/{self.params.drone_count} coverage={snapshot['stats']['coverage']} survivor={snapshot['survivor_found']}"
            )
            write_snapshot_file(self.params.snapshot_path, snapshot)
else:
    class _OperatorNodePlaceholder:  # pragma: no cover - placeholder when ROS deps are unavailable
        pass

    OperatorNode = _OperatorNodePlaceholder
if Node is not None:
    OperatorNode = _OperatorNodeImpl


def main(args: list[str] | None = None) -> int:
    if rclpy is None or Node is None:
        raise RuntimeError(
            "ROS 2 Python runtime is not available. Install ROS 2, build the workspace with colcon, and source install/setup.bash before running entropy_hunt_ros2 nodes."
        )
    rclpy.init(args=args)
    node: Any = OperatorNode()
    try:
        rclpy.spin(node)
    finally:
        if hasattr(node, "_server") and node._server is not None:
            node._server.stop()
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
