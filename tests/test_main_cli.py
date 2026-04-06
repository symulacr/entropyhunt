from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

import main


class _FakeDashboard:
    def __init__(self, *, max_events: int = 8, tick_delay_seconds: float = 0.02) -> None:
        self.max_events = max_events
        self.tick_delay_seconds = tick_delay_seconds

    def build_frame(self, sim_state: dict[str, object]) -> str:
        _ = sim_state
        return ""


def _base_args(tmp_path: Path, **overrides: object) -> Namespace:
    values: dict[str, object] = {
        "mode": "stub",
        "drones": 5,
        "grid": 4,
        "duration": 0,
        "tick_seconds": 1,
        "tick_delay_seconds": 0.25,
        "mesh": "local",
        "record": False,
        "target": "0,0",
        "fail_drone": None,
        "fail_at": 60,
        "stop_on_survivor": False,
        "seed": 7,
        "final_map": str(tmp_path / "final-map.json"),
        "proofs": str(tmp_path / "proofs.jsonl"),
        "control_file": "",
        "svg_map": None,
        "final_html": "",
        "peer_id": "drone_1",
        "host": "127.0.0.1",
        "port": 0,
        "peer": [],
        "transport": "local",
        "mqtt_host": "127.0.0.1",
        "mqtt_port": 1883,
        "mqtt_username": None,
        "mqtt_password": None,
    }
    values.update(overrides)
    return Namespace(**values)


def test_run_stub_mode_accepts_tick_delay_seconds_without_crashing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    delays: list[float] = []
    monkeypatch.setattr(main, "TUIDashboard", _FakeDashboard)
    monkeypatch.setattr(main.time, "sleep", lambda seconds: delays.append(seconds))

    exit_code = main.run_stub_mode(_base_args(tmp_path))

    assert exit_code == 0
    assert delays == [0.25]
    payload = json.loads((tmp_path / "final-map.json").read_text())
    assert payload["summary"]["duration_elapsed"] == 0


def test_run_stub_mode_uses_dashboard_default_tick_delay_when_flag_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays: list[float] = []
    monkeypatch.setattr(main, "TUIDashboard", _FakeDashboard)
    monkeypatch.setattr(main.time, "sleep", lambda seconds: delays.append(seconds))

    exit_code = main.run_stub_mode(_base_args(tmp_path, tick_delay_seconds=None))

    assert exit_code == 0
    assert delays == [_FakeDashboard().tick_delay_seconds]


def test_main_rejects_control_file_outside_peer_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "parse_args", lambda: _base_args(tmp_path, control_file=str(tmp_path / "control.json")))

    with pytest.raises(SystemExit) as excinfo:
        main.main()

    assert str(excinfo.value) == "--control-file is only supported in peer mode"
