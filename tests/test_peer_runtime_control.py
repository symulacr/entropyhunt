from __future__ import annotations

import json
from pathlib import Path

from simulation.peer_runtime import PeerRuntime, PeerRuntimeConfig


def test_peer_runtime_applies_control_file(tmp_path: Path) -> None:
    control_file = tmp_path / "control.json"
    control_file.write_text(
        json.dumps(
            {
                "tick_seconds": 2,
                "tick_delay_seconds": 0.25,
                "requested_drone_count": 7,
            }
        )
    )
    runtime = PeerRuntime(
        PeerRuntimeConfig(
            peer_id="drone_1",
            grid=5,
            duration=5,
            control_file=str(control_file),
        )
    )
    runtime._apply_runtime_control()
    assert runtime._tick_ms() == 2000
    assert runtime._tick_delay_seconds == 0.25
    assert runtime._requested_drone_count == 7
