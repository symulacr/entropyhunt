from __future__ import annotations

import pytest

from entropy_hunt_ros2 import drone_node, operator_node


def test_ros_nodes_fail_with_explicit_runtime_error_when_ros_is_unavailable() -> None:
    with pytest.raises(RuntimeError, match="ROS 2 Python runtime is not available"):
        drone_node.main([])

    with pytest.raises(RuntimeError, match="ROS 2 Python runtime is not available"):
        operator_node.main([])
