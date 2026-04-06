from __future__ import annotations

import json
from pathlib import Path

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


def test_merge_peer_payloads_preserves_claim_identity_and_owner_cells(tmp_path: Path) -> None:
    (tmp_path / "drone_1.json").write_text(
        json.dumps(
            {
                "summary": {
                    "peer_id": "drone_1",
                    "duration_elapsed": 5,
                    "drones": [
                        {"id": "drone_1", "position": [0, 0], "claimed_cell": [1, 1]},
                    ],
                },
                "events": [],
                "grid": [[{"x": 0, "y": 0, "certainty": 0.5}, {"x": 1, "y": 0, "certainty": 0.5}], [{"x": 0, "y": 1, "certainty": 0.5}, {"x": 1, "y": 1, "certainty": 0.7, "owner": "drone_1"}]],
            }
        )
    )
    (tmp_path / "drone_2.json").write_text(
        json.dumps(
            {
                "summary": {
                    "peer_id": "drone_2",
                    "duration_elapsed": 5,
                    "drones": [
                        {"id": "drone_2", "position": [1, 0], "claimed_cell": [0, 1]},
                    ],
                },
                "events": [],
                "grid": [[{"x": 0, "y": 0, "certainty": 0.6}, {"x": 1, "y": 0, "certainty": 0.6}], [{"x": 0, "y": 1, "certainty": 0.8, "owner": "drone_2"}, {"x": 1, "y": 1, "certainty": 0.6}]],
            }
        )
    )

    merged = merge_peer_payloads(tmp_path)

    drones = {drone["id"]: drone for drone in merged["summary"]["drones"]}
    assert drones["drone_1"]["claimed_cell"] == [1, 1]
    assert drones["drone_2"]["claimed_cell"] == [0, 1]
    assert merged["grid"][1][0]["owner"] == "drone_2"
    assert merged["grid"][1][1]["owner"] == "drone_1"
