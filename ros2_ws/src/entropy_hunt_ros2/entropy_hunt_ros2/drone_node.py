"""
Entropy Hunt ROS2 Drone Node (Simulated PX4-Compatible Telemetry)

This node publishes simulated drone telemetry on ROS2 topics using
message schemas that mirror PX4 flight-stack conventions:
- /swarm/drone_state  -> position, altitude, heading, battery, flight_mode
- /swarm/heartbeat    -> alive, reachable, position, altitude, heading, battery

All telemetry fields are simulated (no hardware integration) to ensure
downstream consumers can validate against real PX4 topic layouts.
"""

from __future__ import annotations

import hashlib
import math
import time
from typing import Any

try:
    import rclpy
    from rclpy.node import Node
except ModuleNotFoundError:
    rclpy = None
    Node = None

try:
    from entropy_hunt_interfaces.msg import (
        Claim,
        ConsensusRoundResult,
        DroneState,
        Heartbeat,
        RuntimeControl,
        SurvivorFound,
    )
except ModuleNotFoundError:
    ConsensusRoundResult = Claim = DroneState = Heartbeat = RuntimeControl = SurvivorFound = None

from .parameters import declare_drone_parameters, load_drone_parameters
from .ros_mesh import (
    BINDINGS,
    create_assignment_message,
    create_certainty_update_message,
    create_claim_message,
    create_consensus_result_message,
    create_drone_state_message,
    create_heartbeat_message,
    create_publishers,
    create_subscription,
    create_survivor_found_message,
)

TICK_CHANGE_THRESHOLD = 1e-9
SURVIVOR_CERTAINTY = 0.9
MIN_CONTENDERS_FOR_CONSENSUS = 2
MAX_CLAIM_ZONES = 256

DroneNode: type[Any]

if (
    Node is not None
    and DroneState is not None
    and Heartbeat is not None
    and SurvivorFound is not None
    and Claim is not None
    and ConsensusRoundResult is not None
    and RuntimeControl is not None
):

    class _DroneNodeImpl(Node):
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
            self._consensus_subscription = create_subscription(
                self,
                BINDINGS.consensus_result,
                self._on_consensus_result,
            )
            self._survivor_subscription = create_subscription(
                self,
                BINDINGS.survivor_found,
                self._on_survivor_found,
            )
            self._runtime_control_subscription = create_subscription(
                self,
                BINDINGS.runtime_control,
                self._on_runtime_control,
            )
            self._searched_cells = 0
            self._tick_count = 0
            self._failed = False
            self._survivor_emitted = False
            self._seen_survivor_events: set[tuple[str, int, int]] = set()
            self._position = (0, 0)
            self._target = (self.params.target_x, self.params.target_y)
            self._battery_pct = 100.0
            self._heading_deg = 0.0
            self.get_logger().info(
                f"Drone node {self.params.peer_id} started on "
                f"{BINDINGS.drone_state.name} "
                f"(grid={self.params.grid}, "
                f"target=[{self.params.target_x},{self.params.target_y}])",
            )

        def _set_tick_seconds(self, next_tick_seconds: float) -> None:
            normalized = max(0.05, float(next_tick_seconds))
            if abs(normalized - self._tick_seconds) < TICK_CHANGE_THRESHOLD:
                return
            self.destroy_timer(self.timer)
            self._tick_seconds = normalized
            self.timer = self.create_timer(self._tick_seconds, self._tick)
            self.get_logger().info(
                f"{self.params.peer_id} runtime tick updated to {self._tick_seconds:.2f}s",
            )

        def _trim_claims(self) -> None:
            now_ms = int(time.time() * 1000)
            cutoff_ms = now_ms - 30_000
            # Evict stale drone claims within each cell (F-009)
            for key in list(self._claims.keys()):
                cell = self._claims[key]
                stale = [d for d, ts in cell.items() if ts < cutoff_ms]
                for d in stale:
                    del cell[d]
                if not cell:
                    del self._claims[key]
            # Grid bounds check
            grid = self.params.grid
            valid_keys = [
                key for key in self._claims
                if 0 <= key[0] < grid and 0 <= key[1] < grid
            ]
            evicted = set(self._claims.keys()) - set(valid_keys)
            for key in evicted:
                del self._claims[key]
            if len(self._claims) > MAX_CLAIM_ZONES:
                sorted_keys = sorted(
                    self._claims.keys(),
                    key=lambda k: max(self._claims[k].values()),
                )
                for key in sorted_keys[: len(self._claims) - MAX_CLAIM_ZONES]:
                    del self._claims[key]

        def _derive_contest_id(self, key: tuple[int, int], contenders: dict[str, int]) -> str:
            # F-010: deterministic hash over sorted contender IDs
            sorted_ids = ",".join(sorted(contenders.keys()))
            base = f"{key[0]}:{key[1]}:{sorted_ids}"
            digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:8]
            return f"{key[0]}:{key[1]}:{digest}"

        def _on_claim(self, message: Any) -> None:
            try:
                key = (int(message.x), int(message.y))
                self._claims.setdefault(key, {})[str(message.drone_id)] = int(message.timestamp_ms)
                contenders = self._claims[key]
                if len(contenders) < MIN_CONTENDERS_FOR_CONSENSUS:
                    return
                winner = min(contenders)
                if self.params.peer_id != winner:
                    return
                contest_id = self._derive_contest_id(key, contenders)
                if contest_id == self._last_result_contest_id:
                    return
                self._last_result_contest_id = contest_id
                self._round_id += 1
                assignments = []
                for contender in sorted(contenders):
                    if contender == winner:
                        assignments.append(
                            create_assignment_message(
                                drone_id=contender,
                                x=key[0],
                                y=key[1],
                                reason="winner",
                            ),
                        )
                    else:
                        fallback_x = min(self.params.grid - 1, key[0] + 1)
                        fallback_y = key[1]
                        assignments.append(
                            create_assignment_message(
                                drone_id=contender,
                                x=fallback_x,
                                y=fallback_y,
                                reason="reassigned",
                            ),
                        )
                self._mesh_publishers["consensus_result"].publish(
                    create_consensus_result_message(
                        round_id=self._round_id,
                        contest_id=contest_id,
                        x=key[0],
                        y=key[1],
                        rationale=f"winner={winner}; contenders={len(contenders)}",
                        assignments=assignments,
                    ),
                )
            except Exception as e:
                self.get_logger().error(f"_on_claim error: {e}")
                return

        def _on_consensus_result(self, message: Any) -> None:
            try:
                for assignment in getattr(message, "assignments", []):
                    if str(assignment.drone_id) != self.params.peer_id:
                        continue
                    self._target = (int(assignment.x), int(assignment.y))
                    self._assignment_reason = str(assignment.reason)
            except Exception as e:
                self.get_logger().error(f"_on_consensus_result error: {e}")
                return

        def _on_survivor_found(self, message: Any) -> None:
            try:
                event_key = (str(message.drone_id), int(message.x), int(message.y))
                if event_key in self._seen_survivor_events:
                    return
                self._seen_survivor_events.add(event_key)
                self.get_logger().info(
                    f"{self.params.peer_id} observed survivor confirmation "
                    f"from {message.drone_id} "
                    f"at [{message.x},{message.y}]",
                )
            except Exception as e:
                self.get_logger().error(f"_on_survivor_found error: {e}")
                return

        def _on_runtime_control(self, message: Any) -> None:
            try:
                next_tick = float(getattr(message, "tick_seconds", 0.0))
                if next_tick > 0:
                    self._set_tick_seconds(next_tick)
            except Exception as e:
                self.get_logger().error(f"_on_runtime_control error: {e}")
                return

        def _advance_position(self) -> None:
            px, py = self._position
            tx, ty = self._target
            if px != tx:
                px += 1 if tx > px else -1
            elif py != ty:
                py += 1 if ty > py else -1
            self._position = (px, py)

        def _tick(self) -> None:
            try:
                self._tick_count += 1
                self._elapsed_seconds += self._tick_seconds
                if self.params.fail_at >= 0 and self._elapsed_seconds >= self.params.fail_at:
                    if not self._failed:
                        self._failed = True
                        self.get_logger().warning(
                            f"{self.params.peer_id} entering fail_at silence mode",
                        )
                    return
                self._advance_position()
                self._searched_cells += 1
                certainty = min(0.95, 0.5 + 0.05 * self._searched_cells)
                claim_id = (
                    f"{self.params.peer_id}:{self._target[0]}:{self._target[1]}:{self._tick_count}"
                )
                # Simulated PX4-compatible telemetry
                self._battery_pct = max(0.0, self._battery_pct - 0.02)
                altitude_m = 15.0 + 2.0 * math.sin(self._tick_count * 0.1)
                px, py = self._position
                tx, ty = self._target
                if px < tx:
                    self._heading_deg = 90.0
                elif px > tx:
                    self._heading_deg = 270.0
                elif py < ty:
                    self._heading_deg = 0.0
                elif py > ty:
                    self._heading_deg = 180.0
                flight_mode = "AUTO_MISSION" if self._position == self._target else "OFFBOARD"
                self._mesh_publishers["claims"].publish(
                    create_claim_message(
                        claim_id=claim_id,
                        drone_id=self.params.peer_id,
                        x=self._target[0],
                        y=self._target[1],
                        timestamp_ms=int(time.time() * 1000),
                    ),
                )
                self._mesh_publishers["heartbeat"].publish(
                    create_heartbeat_message(
                        drone_id=self.params.peer_id,
                        x=self._position[0],
                        y=self._position[1],
                        alive=True,
                        reachable=True,
                        timestamp_ms=int(time.time() * 1000),
                        altitude_m=altitude_m,
                        heading_deg=self._heading_deg,
                        battery_pct=self._battery_pct,
                        flight_mode=flight_mode,
                    ),
                )
                self._mesh_publishers["drone_state"].publish(
                    create_drone_state_message(
                        drone_id=self.params.peer_id,
                        x=self._position[0],
                        y=self._position[1],
                        tx=self._target[0],
                        ty=self._target[1],
                        status="searching"
                        if self._position == self._target
                        else f"transit:{self._assignment_reason}",
                        alive=True,
                        reachable=True,
                        searched_cells=self._searched_cells,
                        altitude_m=altitude_m,
                        heading_deg=self._heading_deg,
                        battery_pct=self._battery_pct,
                        flight_mode=flight_mode,
                    ),
                )
                self._mesh_publishers["certainty_update"].publish(
                    create_certainty_update_message(
                        updated_by=self.params.peer_id,
                        x=self._position[0],
                        y=self._position[1],
                        certainty=certainty,
                    ),
                )
                if (
                    self._position == self._target
                    and certainty >= SURVIVOR_CERTAINTY
                    and not self._survivor_emitted
                ):
                    self._survivor_emitted = True
                    self._mesh_publishers["survivor_found"].publish(
                        create_survivor_found_message(
                            drone_id=self.params.peer_id,
                            x=self._position[0],
                            y=self._position[1],
                            confidence=certainty,
                        ),
                    )
                self._trim_claims()
            except Exception as e:
                self.get_logger().error(f"_tick error: {e}")
                return
else:

    class _DroneNodePlaceholder:
        pass

    DroneNode = _DroneNodePlaceholder
if (
    Node is not None
    and DroneState is not None
    and Heartbeat is not None
    and SurvivorFound is not None
    and Claim is not None
    and ConsensusRoundResult is not None
    and RuntimeControl is not None
):
    DroneNode = _DroneNodeImpl


def main(args: list[str] | None = None) -> int:
    if (
        rclpy is None
        or Node is None
        or DroneState is None
        or Heartbeat is None
        or SurvivorFound is None
        or Claim is None
        or ConsensusRoundResult is None
    ):
        raise RuntimeError(
            "ROS 2 Python runtime is not available. Install ROS 2, "
            "build the workspace with colcon, and source install/setup.bash "
            "before running entropy_hunt_ros2 nodes.",
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
