from __future__ import annotations

from ros2_ws.src.entropy_hunt_ros2.entropy_hunt_ros2.operator_state import OperatorState
from ros2_ws.src.entropy_hunt_ros2.entropy_hunt_ros2.snapshot_builder import (
    apply_certainty_update,
    apply_drone_state,
    apply_heartbeat,
    apply_survivor_found,
    build_snapshot,
)


def test_snapshot_builder_aggregates_state() -> None:
    state = OperatorState.create(drone_count=2, grid_size=4)
    apply_drone_state(
        state,
        drone_id='drone_1',
        x=1,
        y=2,
        tx=3,
        ty=3,
        status='searching',
        alive=True,
        reachable=True,
        searched_cells=5,
    )
    apply_heartbeat(state, drone_id='drone_1', timestamp_ms=1234, alive=True, reachable=True)
    apply_certainty_update(state, x=1, y=2, certainty=0.91)
    apply_survivor_found(state, drone_id='drone_1', x=3, y=3, confidence=0.97, timestamp_ms=2000)

    snapshot = build_snapshot(state, elapsed_seconds=12)
    assert snapshot['t'] == 12
    assert snapshot['survivor_found'] is True
    assert snapshot['stats']['coverage'] > 0
    assert snapshot['drones'][0]['drone_id'] == 'drone_1'
    assert snapshot['grid'][2][1]['certainty'] == 0.91
    assert snapshot['events'][-1]['event_type'] == 'survivor_found'
