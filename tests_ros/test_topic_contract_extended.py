from __future__ import annotations

from ros2_ws.src.entropy_hunt_ros2.entropy_hunt_ros2.ros_mesh import BINDINGS


def test_bindings_cover_all_primary_swarm_topics() -> None:
    assert BINDINGS.heartbeat.name == '/swarm/heartbeat'
    assert BINDINGS.drone_state.name == '/swarm/drone_state'
    assert BINDINGS.claims.name == '/swarm/claims'
    assert BINDINGS.bft_result.name == '/swarm/bft_result'
    assert BINDINGS.certainty_update.name == '/swarm/certainty_update'
    assert BINDINGS.survivor_found.name == '/swarm/survivor_found'
    assert BINDINGS.runtime_control.name == '/swarm/runtime_control'
