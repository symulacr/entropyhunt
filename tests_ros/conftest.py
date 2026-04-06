from __future__ import annotations

import sys
from pathlib import Path


ROS2_PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "ros2_ws" / "src" / "entropy_hunt_ros2"
if str(ROS2_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(ROS2_PACKAGE_ROOT))
