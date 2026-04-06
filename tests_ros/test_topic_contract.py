from __future__ import annotations

from ros2_ws.src.entropy_hunt_ros2.entropy_hunt_ros2 import topic_names


def test_topic_names_are_unique() -> None:
    values = [
        topic_names.HEARTBEAT_TOPIC,
        topic_names.DRONE_STATE_TOPIC,
        topic_names.CLAIMS_TOPIC,
        topic_names.BFT_RESULT_TOPIC,
        topic_names.CERTAINTY_UPDATE_TOPIC,
        topic_names.SURVIVOR_FOUND_TOPIC,
        topic_names.RUNTIME_CONTROL_TOPIC,
    ]
    assert len(values) == len(set(values))
    assert all(value.startswith('/swarm/') for value in values)
