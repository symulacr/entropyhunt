from __future__ import annotations

import time
from typing import Any

try:
    import rclpy
    from rclpy.node import Node
except ModuleNotFoundError:
    rclpy = None
    Node = None  # type: ignore[assignment]

try:
    from entropy_hunt_interfaces.msg import BftRoundResult, Claim, DroneState, Heartbeat, RuntimeControl, SurvivorFound
except ModuleNotFoundError:
    BftRoundResult = Claim = DroneState = Heartbeat = RuntimeControl = SurvivorFound = None  # type: ignore[assignment]

from .parameters import declare_drone_parameters, load_drone_parameters
from .ros_mesh import (
    BINDINGS,
    create_assignment_message,
    create_bft_result_message,
    create_certainty_update_message,
    create_claim_message,
    create_drone_state_message,
    create_heartbeat_message,
    create_publishers,
    create_subscription,
    create_survivor_found_message,
)


if Node is not None and DroneState is not None and Heartbeat is not None and SurvivorFound is not None and Claim is not None and BftRoundResult is not None and RuntimeControl is not None:
    class DroneNode(Node):
        def __init__(self) -> None:
            super().__init__("entropy_hunt_drone")
            declare_drone_parameters(self)
            self.params = load_drone_parameters(self)
            self._mesh_publishers = create_publishers(self)
            self._claims: dict[tuple[int, int], dict[str, int]] = {}
            self._round_id = 0
            self._assignment_reason = "initial"
            self._last_result_contest_id: str | None = None
            self._tick_seconds = float(self.params.tick_seconds)
            self._elapsed_seconds = 0.0
            self.timer = self.create_timer(self._tick_seconds, self._tick)
            self._claim_subscription = create_subscription(self, BINDINGS.claims, self._on_claim)
            self._bft_subscription = create_subscription(self, BINDINGS.bft_result, self._on_bft_result)
            self._survivor_subscription = create_subscription(self, BINDINGS.survivor_found, self._on_survivor_found)
            self._runtime_control_subscription = create_subscription(self, BINDINGS.runtime_control, self._on_runtime_control)
            self._searched_cells = 0
            self._tick_count = 0
            self._failed = False
            self._survivor_emitted = False
            self._seen_survivor_events: set[tuple[str, int, int]] = set()
            self._position = (0, 0)
            self._target = (self.params.target_x, self.params.target_y)
            self.get_logger().info(
                f"Drone node {self.params.peer_id} started on {BINDINGS.drone_state.name} (grid={self.params.grid}, target=[{self.params.target_x},{self.params.target_y}])"
            )

        def _set_tick_seconds(self, next_tick_seconds: float) -> None:
            normalized = max(0.05, float(next_tick_seconds))
            if abs(normalized - self._tick_seconds) < 1e-9:
                return
            self.destroy_timer(self.timer)
            self._tick_seconds = normalized
            self.timer = self.create_timer(self._tick_seconds, self._tick)
            self.get_logger().info(f"{self.params.peer_id} runtime tick updated to {self._tick_seconds:.2f}s")

        def _on_claim(self, message: Any) -> None:
            key = (int(message.x), int(message.y))
            self._claims.setdefault(key, {})[str(message.drone_id)] = int(message.timestamp_ms)
            contenders = self._claims[key]
            if len(contenders) < 2:
                return
            winner = min(contenders)
            if self.params.peer_id != winner:
                return
            contest_id = f"{key[0]}:{key[1]}:{len(contenders)}"
            if contest_id == self._last_result_contest_id:
                return
            self._last_result_contest_id = contest_id
            self._round_id += 1
            assignments = []
            for contender in sorted(contenders):
                if contender == winner:
                    assignments.append(create_assignment_message(drone_id=contender, x=key[0], y=key[1], reason="winner"))
                else:
                    fallback_x = min(self.params.grid - 1, key[0] + 1)
                    fallback_y = key[1]
                    assignments.append(create_assignment_message(drone_id=contender, x=fallback_x, y=fallback_y, reason="reassigned"))
            self._mesh_publishers["bft_result"].publish(
                create_bft_result_message(
                    round_id=self._round_id,
                    contest_id=contest_id,
                    x=key[0],
                    y=key[1],
                    rationale=f"winner={winner}; contenders={len(contenders)}",
                    assignments=assignments,
                )
            )

        def _on_bft_result(self, message: Any) -> None:
            for assignment in getattr(message, "assignments", []):
                if str(assignment.drone_id) != self.params.peer_id:
                    continue
                self._target = (int(assignment.x), int(assignment.y))
                self._assignment_reason = str(assignment.reason)

        def _on_survivor_found(self, message: Any) -> None:
            event_key = (str(message.drone_id), int(message.x), int(message.y))
            if event_key in self._seen_survivor_events:
                return
            self._seen_survivor_events.add(event_key)
            self.get_logger().info(
                f"{self.params.peer_id} observed survivor confirmation from {message.drone_id} at [{message.x},{message.y}]"
            )

        def _on_runtime_control(self, message: Any) -> None:
            next_tick = float(getattr(message, "tick_seconds", 0.0))
            if next_tick > 0:
                self._set_tick_seconds(next_tick)

        def _advance_position(self) -> None:
            px, py = self._position
            tx, ty = self._target
            if px != tx:
                px += 1 if tx > px else -1
            elif py != ty:
                py += 1 if ty > py else -1
            self._position = (px, py)

        def _tick(self) -> None:
            self._tick_count += 1
            self._elapsed_seconds += self._tick_seconds
            if self.params.fail_at >= 0 and self._elapsed_seconds >= self.params.fail_at:
                if not self._failed:
                    self._failed = True
                    self.get_logger().warning(f"{self.params.peer_id} entering fail_at silence mode")
                return
            self._advance_position()
            self._searched_cells += 1
            certainty = min(0.95, 0.5 + 0.05 * self._searched_cells)
            claim_id = f"{self.params.peer_id}:{self._target[0]}:{self._target[1]}:{self._tick_count}"
            self._mesh_publishers["claims"].publish(
                create_claim_message(
                    claim_id=claim_id,
                    drone_id=self.params.peer_id,
                    x=self._target[0],
                    y=self._target[1],
                    timestamp_ms=int(time.time() * 1000),
                )
            )
            self._mesh_publishers["heartbeat"].publish(
                create_heartbeat_message(
                    drone_id=self.params.peer_id,
                    x=self._position[0],
                    y=self._position[1],
                    alive=True,
                    reachable=True,
                    timestamp_ms=int(time.time() * 1000),
                )
            )
            self._mesh_publishers["drone_state"].publish(
                create_drone_state_message(
                    drone_id=self.params.peer_id,
                    x=self._position[0],
                    y=self._position[1],
                    tx=self._target[0],
                    ty=self._target[1],
                    status="searching" if self._position == self._target else f"transit:{self._assignment_reason}",
                    alive=True,
                    reachable=True,
                    searched_cells=self._searched_cells,
                )
            )
            self._mesh_publishers["certainty_update"].publish(
                create_certainty_update_message(
                    updated_by=self.params.peer_id,
                    x=self._position[0],
                    y=self._position[1],
                    certainty=certainty,
                )
            )
            if self._position == self._target and certainty >= 0.9 and not self._survivor_emitted:
                self._survivor_emitted = True
                self._mesh_publishers["survivor_found"].publish(
                    create_survivor_found_message(
                        drone_id=self.params.peer_id,
                        x=self._position[0],
                        y=self._position[1],
                        confidence=certainty,
                    )
                )
else:
    class DroneNode:  # pragma: no cover - placeholder when ROS deps are unavailable
        pass


def main(args: list[str] | None = None) -> int:
    if rclpy is None or Node is None or DroneState is None or Heartbeat is None or SurvivorFound is None or Claim is None or BftRoundResult is None:
        raise RuntimeError(
            "ROS 2 Python runtime is not available. Install ROS 2, build the workspace with colcon, and source install/setup.bash before running entropy_hunt_ros2 nodes."
        )
    rclpy.init(args=args)
    node: Any = DroneNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
