from __future__ import annotations

from pathlib import Path


EXPECTED_FILES = [
    Path('ros2_ws/src/entropy_hunt_interfaces/package.xml'),
    Path('ros2_ws/src/entropy_hunt_interfaces/CMakeLists.txt'),
    Path('ros2_ws/src/entropy_hunt_interfaces/msg/Heartbeat.msg'),
    Path('ros2_ws/src/entropy_hunt_interfaces/msg/DroneState.msg'),
    Path('ros2_ws/src/entropy_hunt_interfaces/msg/RuntimeControl.msg'),
    Path('ros2_ws/src/entropy_hunt_ros2/package.xml'),
    Path('ros2_ws/src/entropy_hunt_ros2/setup.py'),
    Path('ros2_ws/src/entropy_hunt_ros2/launch/demo.launch.py'),
    Path('ros2_ws/src/entropy_hunt_ros2/entropy_hunt_ros2/drone_node.py'),
    Path('ros2_ws/src/entropy_hunt_ros2/entropy_hunt_ros2/operator_node.py'),
    Path('ros2_ws/src/entropy_hunt_ros2/entropy_hunt_ros2/ros_mesh.py'),
]


def test_ros_phase2_scaffold_files_exist() -> None:
    missing = [str(path) for path in EXPECTED_FILES if not path.exists()]
    assert not missing, f'Missing ROS scaffold files: {missing}'
