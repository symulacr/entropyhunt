from __future__ import annotations
# mypy: disable-error-code=attr-defined

from typing import Any

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _launch_setup(context: Any, *_args: Any, **_kwargs: Any) -> list[Any]:
    count = int(LaunchConfiguration("count").perform(context))
    grid = int(LaunchConfiguration("grid").perform(context))
    target_x = int(LaunchConfiguration("target_x").perform(context))
    target_y = int(LaunchConfiguration("target_y").perform(context))
    tick_seconds = float(LaunchConfiguration("tick_seconds").perform(context))
    fail_drone = LaunchConfiguration("fail_drone").perform(context)
    fail_at = int(LaunchConfiguration("fail_at").perform(context))
    snapshot_path = LaunchConfiguration("snapshot_path").perform(context)
    snapshot_host = LaunchConfiguration("snapshot_host").perform(context)
    snapshot_port = int(LaunchConfiguration("snapshot_port").perform(context))

    actions = [
        Node(
            package="entropy_hunt_ros2",
            executable="operator_node",
            name="entropy_hunt_operator",
            parameters=[{"drone_count": count, "grid": grid, "target_x": target_x, "target_y": target_y, "tick_seconds": tick_seconds, "snapshot_path": snapshot_path, "snapshot_host": snapshot_host, "snapshot_port": snapshot_port}],
            output="screen",
        )
    ]
    for index in range(count):
        peer_id = f"drone_{index + 1}"
        actions.append(
            Node(
                package="entropy_hunt_ros2",
                executable="drone_node",
                name=peer_id,
                parameters=[
                    {
                        "peer_id": peer_id,
                        "grid": grid,
                        "target_x": target_x,
                        "target_y": target_y,
                        "tick_seconds": tick_seconds,
                        "fail_at": fail_at if peer_id == fail_drone else -1,
                    }
                ],
                output="screen",
            )
        )
    return actions


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(
        [
            DeclareLaunchArgument("count", default_value="2"),
            DeclareLaunchArgument("grid", default_value="10"),
            DeclareLaunchArgument("target_x", default_value="7"),
            DeclareLaunchArgument("target_y", default_value="3"),
            DeclareLaunchArgument("tick_seconds", default_value="1.0"),
            DeclareLaunchArgument("fail_drone", default_value="drone_2"),
            DeclareLaunchArgument("fail_at", default_value="60"),
            DeclareLaunchArgument("snapshot_path", default_value=""),
            DeclareLaunchArgument("snapshot_host", default_value="127.0.0.1"),
            DeclareLaunchArgument("snapshot_port", default_value="8776"),
            OpaqueFunction(function=_launch_setup),
        ]
    )
