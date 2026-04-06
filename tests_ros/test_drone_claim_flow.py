from __future__ import annotations

from ros2_ws.src.entropy_hunt_ros2.entropy_hunt_ros2.snapshot_builder import (
    apply_bft_result,
    apply_claim,
    build_snapshot,
)
from ros2_ws.src.entropy_hunt_ros2.entropy_hunt_ros2.operator_state import OperatorState


def test_claim_and_bft_result_update_operator_state() -> None:
    state = OperatorState.create(drone_count=3, grid_size=5)
    apply_claim(state, claim_id='d1:2:3:1', drone_id='drone_1', x=2, y=3, timestamp_ms=1000)
    apply_claim(state, claim_id='d2:2:3:1', drone_id='drone_2', x=2, y=3, timestamp_ms=1001)
    apply_bft_result(
        state,
        contest_id='2:3:2',
        x=2,
        y=3,
        assignments=[
            {'drone_id': 'drone_1', 'x': 2, 'y': 3, 'reason': 'winner'},
            {'drone_id': 'drone_2', 'x': 3, 'y': 3, 'reason': 'reassigned'},
        ],
        rationale='winner=drone_1; contenders=2',
        timestamp_ms=1200,
    )
    snapshot = build_snapshot(state, elapsed_seconds=2)
    assert snapshot['stats']['auctions'] >= 2
    assert snapshot['stats']['bft_rounds'] == 1
    assert snapshot['grid'][3][2]['owner'] == 0
