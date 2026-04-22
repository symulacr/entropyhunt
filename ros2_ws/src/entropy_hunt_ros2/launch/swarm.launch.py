from __future__ import annotations

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        Node(
            package="entropy_hunt_ros2",
            executable="operator_node",
            name="entropy_hunt_operator",
            output="screen",
        ),
        Node(
            package="entropy_hunt_ros2",
            executable="drone_node",
            name="drone_1",
            output="screen",
        ),
    ])
