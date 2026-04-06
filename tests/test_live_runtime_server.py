from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import serve_live_runtime
from scripts.serve_live_runtime import merge_peer_payloads


def test_merge_peer_payloads_combines_drones_and_events(tmp_path: Path) -> None:
    first = {
        "summary": {
            "peer_id": "drone_1",
            "duration_elapsed": 2,
            "mesh_messages": 4,
            "bft_rounds": 1,
            "dropouts": 0,
            "survivor_receipts": 0,
            "drones": [{"id": "drone_1", "position": [0, 0]}],
        },
        "events": [{"t": 1, "type": "mesh", "message": "ready"}],
        "grid": [[{"certainty": 0.5}]],
    }
    second = {
        "summary": {
            "peer_id": "drone_2",
            "duration_elapsed": 3,
            "mesh_messages": 5,
            "bft_rounds": 2,
            "dropouts": 1,
            "survivor_receipts": 1,
            "drones": [{"id": "drone_2", "position": [1, 1]}],
        },
        "events": [{"t": 2, "type": "bft", "message": "resolved"}],
        "grid": [[{"certainty": 0.9}]],
    }
    (tmp_path / "drone_1.json").write_text(json.dumps(first))
    (tmp_path / "drone_2.json").write_text(json.dumps(second))

    merged = merge_peer_payloads(tmp_path)
    assert merged["summary"]["peer_count"] == 2
    assert merged["summary"]["mesh_messages"] == 9
    assert merged["summary"]["bft_rounds"] == 2
    assert merged["summary"]["dropouts"] == 1
    assert len(merged["summary"]["drones"]) == 2
    assert len(merged["events"]) == 2
    assert merged["grid"] == [[{"certainty": 0.9}]]


def test_merge_peer_payloads_ignores_control_file_for_peer_count(tmp_path: Path) -> None:
    peer = {
        "summary": {
            "peer_id": "drone_1",
            "duration_elapsed": 1,
            "drones": [{"id": "drone_1", "position": [0, 0]}],
        },
        "config": {"drone_count": 1, "tick_seconds": 1},
        "events": [],
        "grid": [[{"certainty": 0.5, "entropy": 1.0, "x": 0, "y": 0}]],
    }
    (tmp_path / "drone_1.json").write_text(json.dumps(peer))
    (tmp_path / "control.json").write_text(
        json.dumps({"tick_delay_seconds": 0.2, "requested_drone_count": 4})
    )

    merged = merge_peer_payloads(tmp_path)

    assert merged["summary"]["peer_count"] == 1
    assert merged["config"]["requested_drone_count"] == 4
    assert merged["config"]["tick_delay_seconds"] == 0.2
    assert merged["config"]["source_mode"] == "peer-merged-live"
    assert merged["config"]["snapshot_provenance"] == "merged-live"
    assert merged["config"]["synthetic"] is False


def test_merge_peer_payloads_returns_control_config_without_runtime_payloads(tmp_path: Path) -> None:
    (tmp_path / "control.json").write_text(
        json.dumps({"tick_delay_seconds": 0.15, "requested_drone_count": 4})
    )

    merged = merge_peer_payloads(tmp_path)

    assert merged["summary"]["peer_count"] == 0
    assert merged["summary"]["drones"] == []
    assert merged["config"]["tick_delay_seconds"] == 0.15
    assert merged["config"]["requested_drone_count"] == 4
    assert merged["config"]["control_url"] == "/control"
    assert merged["config"]["source_mode"] == "peer-merged-live"
    assert merged["config"]["snapshot_provenance"] == "control-only-placeholder"
    assert merged["config"]["synthetic"] is True


def test_snapshot_http_server_caches_merged_payload_until_snapshot_files_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "drone_1.json").write_text(
        json.dumps(
            {
                "summary": {"duration_elapsed": 1, "drones": [{"id": "drone_1"}]},
                "config": {"drone_count": 1},
                "grid": [[{"certainty": 0.5, "entropy": 1.0, "x": 0, "y": 0}]],
                "events": [],
            }
        )
    )

    calls: list[dict[str, Any]] = []
    original_merge = serve_live_runtime.merge_peer_payloads

    def counting_merge(snapshot_dir: Path) -> dict[str, Any]:
        merged = original_merge(snapshot_dir)
        calls.append(merged)
        return merged

    monkeypatch.setattr(serve_live_runtime, "merge_peer_payloads", counting_merge)
    server = serve_live_runtime.SnapshotHTTPServer(
        ("127.0.0.1", 0),
        serve_live_runtime.LiveRuntimeRequestHandler,
        snapshot_dir=tmp_path,
    )
    try:
        first = server.get_merged_payload()
        second = server.get_merged_payload()

        assert first is second
        assert len(calls) == 1

        (tmp_path / "control.json").write_text(json.dumps({"tick_delay_seconds": 0.25}))
        third = server.get_merged_payload()

        assert len(calls) == 2
        assert third["config"]["tick_delay_seconds"] == 0.25
    finally:
        server.server_close()
