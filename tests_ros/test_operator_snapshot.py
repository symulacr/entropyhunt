from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

from ros2_ws.src.entropy_hunt_ros2.entropy_hunt_ros2.operator_server import OperatorSnapshotServer, write_snapshot_file
from ros2_ws.src.entropy_hunt_ros2.entropy_hunt_ros2.operator_state import OperatorState
from ros2_ws.src.entropy_hunt_ros2.entropy_hunt_ros2.snapshot_builder import build_snapshot


def test_operator_snapshot_file_write(tmp_path: Path) -> None:
    state = OperatorState.create(drone_count=1, grid_size=3)
    payload = build_snapshot(state, elapsed_seconds=4)
    out = tmp_path / 'snapshot.json'
    write_snapshot_file(str(out), payload)
    assert out.exists()
    assert '"survivor_found": false' in out.read_text()


def test_operator_server_exposes_writable_control_endpoint() -> None:
    snapshot_payload = {"config": {"control_url": "/control"}, "stats": {}, "events": [], "grid": []}
    control_payload = {
        "tick_seconds": 1.0,
        "requested_drone_count": 3,
        "control_capabilities": {
            "tick_seconds": "live",
            "tick_delay_seconds": "unavailable",
            "requested_drone_count": "next_run",
        },
        "status": "writable",
    }
    updates: list[dict[str, object]] = []

    def update_control(payload: dict[str, object]) -> dict[str, object]:
        updates.append(payload)
        control_payload.update(payload)
        return control_payload

    server = OperatorSnapshotServer("127.0.0.1", 0, lambda: snapshot_payload, lambda: control_payload, update_control)
    server.start()
    try:
        port = server._server.server_address[1]
        with urlopen(f"http://127.0.0.1:{port}/control") as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["status"] == "writable"
        assert payload["control_capabilities"]["tick_seconds"] == "live"

        request = Request(
            f"http://127.0.0.1:{port}/control",
            data=json.dumps({"tick_seconds": 0.5, "requested_drone_count": 5}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            updated = json.loads(response.read().decode("utf-8"))
        assert updated["tick_seconds"] == 0.5
        assert updated["requested_drone_count"] == 5
        assert updates[-1] == {"tick_seconds": 0.5, "requested_drone_count": 5}
    finally:
        server.stop()
