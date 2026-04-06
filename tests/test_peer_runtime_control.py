from __future__ import annotations

import json
from pathlib import Path

import pytest

from simulation.peer_runtime import (
    TARGET_FORCE_AT_MS,
    PeerFailureExit,
    PeerRuntime,
    PeerRuntimeConfig,
    _starting_position,
)


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


def test_peer_runtime_failure_raises_nonzero_exit_and_writes_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("simulation.peer_runtime.time.sleep", lambda _: None)
    output_path = tmp_path / "drone_1.json"
    runtime = PeerRuntime(
        PeerRuntimeConfig(
            peer_id="drone_1",
            grid=4,
            duration=5,
            tick_delay_seconds=0.0,
            fail_at=1,
            final_map_path=str(output_path),
            proofs_path=str(tmp_path / "proofs.jsonl"),
        )
    )

    with pytest.raises(PeerFailureExit) as excinfo:
        runtime.run()

    assert excinfo.value.exit_code == 2
    payload = json.loads(output_path.read_text())
    assert payload["summary"]["duration_elapsed"] == 1
    assert any(event["type"] == "failure" for event in payload["events"])


def test_peer_runtime_spreads_start_positions_across_perimeter() -> None:
    peer_ids = [f"drone_{index}" for index in range(1, 6)]

    positions = {_starting_position(peer_id, peer_ids, 6) for peer_id in peer_ids}

    assert len(positions) == len(peer_ids)
    assert positions != {(0, 0)}
    assert all(x in {0, 5} or y in {0, 5} for x, y in positions)


def test_peer_runtime_steps_toward_targets_instead_of_teleporting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("simulation.peer_runtime.time.sleep", lambda _: None)
    runtime = PeerRuntime(
        PeerRuntimeConfig(
            peer_id="drone_1",
            grid=6,
            duration=5,
            tick_delay_seconds=0.0,
            target=(5, 3),
        )
    )
    runtime.bootstrap()
    runtime.local_drone.set_assignment((5, 0))

    runtime.tick()

    assert runtime.local_drone.position == (1, 0)
    assert runtime.local_drone.status == "transiting"
    assert runtime.local_drone.searched_cells == 0


def test_peer_runtime_logs_when_target_probe_is_forced() -> None:
    runtime = PeerRuntime(
        PeerRuntimeConfig(
            peer_id="drone_1",
            grid=6,
            duration=5,
            tick_delay_seconds=0.0,
            target=(5, 3),
        )
    )
    runtime.now_ms = TARGET_FORCE_AT_MS

    runtime._maybe_claim_zone()

    assert any(event["type"] == "forced_target_probe" for event in runtime.events)


def test_peer_runtime_snapshot_exports_claimed_cells_and_owner_rows(tmp_path: Path) -> None:
    output_path = tmp_path / "snapshot.json"
    runtime = PeerRuntime(
        PeerRuntimeConfig(
            peer_id="drone_1",
            grid=4,
            duration=5,
            tick_delay_seconds=0.0,
            final_map_path=str(output_path),
        )
    )
    runtime.local_drone.set_assignment((1, 1))
    runtime.save_final_map(output_path)

    payload = json.loads(output_path.read_text())
    assert payload["summary"]["drones"][0]["claimed_cell"] == [1, 1]
    assert payload["grid"][1][1]["owner"] == "drone_1"
    assert payload["local_grid"][1][1]["owner"] == "drone_1"
    assert payload["config"]["source_mode"] == "peer"
    assert payload["config"]["snapshot_provenance"] == "peer-runtime-export"
    assert payload["config"]["control_capabilities"]["requested_drone_count"] == "unavailable"
