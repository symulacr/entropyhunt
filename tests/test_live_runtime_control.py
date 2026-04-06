from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.request import Request, urlopen

from scripts import serve_live_runtime


def test_merge_peer_payloads_includes_control_config(tmp_path: Path) -> None:
    (tmp_path / "drone_1.json").write_text(
        json.dumps(
            {
                "summary": {"duration_elapsed": 1, "drones": [{"id": "drone_1"}]},
                "config": {"drone_count": 2, "tick_seconds": 1},
                "grid": [[{"certainty": 0.5, "entropy": 1.0, "x": 0, "y": 0}]],
                "events": [],
            }
        )
    )
    (tmp_path / "control.json").write_text(
        json.dumps({"tick_delay_seconds": 0.2, "requested_drone_count": 4})
    )

    merged = serve_live_runtime.merge_peer_payloads(tmp_path)
    assert merged["config"]["tick_delay_seconds"] == 0.2
    assert merged["config"]["requested_drone_count"] == 4
    assert merged["config"]["control_url"] == "/control"


def test_control_endpoint_updates_control_file(tmp_path: Path) -> None:
    (tmp_path / "drone_1.json").write_text(
        json.dumps(
            {
                "summary": {"duration_elapsed": 1, "drones": [{"id": "drone_1"}]},
                "config": {"drone_count": 2, "tick_seconds": 1},
                "grid": [[{"certainty": 0.5, "entropy": 1.0, "x": 0, "y": 0}]],
                "events": [],
            }
        )
    )

    server = serve_live_runtime.SnapshotHTTPServer(("127.0.0.1", 0), serve_live_runtime.LiveRuntimeRequestHandler, snapshot_dir=tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        request = Request(
            f"http://127.0.0.1:{port}/control",
            data=json.dumps({"tick_delay_seconds": 0.15, "requested_drone_count": 6}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["tick_delay_seconds"] == 0.15
        assert payload["requested_drone_count"] == 6

        with urlopen(f"http://127.0.0.1:{port}/snapshot.json") as response:
            snapshot = json.loads(response.read().decode("utf-8"))
        assert snapshot["config"]["requested_drone_count"] == 6
        assert snapshot["config"]["tick_delay_seconds"] == 0.15
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)
