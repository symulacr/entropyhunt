# ruff: noqa: E402
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.tui import TUIDashboard
from core.certainty_map import shannon_entropy
from scripts.serve_live_runtime import merge_peer_payloads


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor the live Entropy Hunt peer swarm in the terminal")
    parser.add_argument("--source", default="http://127.0.0.1:8765/snapshot.json")
    parser.add_argument("--interval-ms", type=int, default=500)
    parser.add_argument("--idle-exit-ms", type=int, default=5000)
    return parser.parse_args()


def _fetch_json(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=2.0) as response:  # noqa: S310 - trusted local demo endpoint
        return json.loads(response.read().decode("utf-8"))


def _grid_entropy(grid: list[list[dict[str, Any]]], position: tuple[int, int] | list[int] | None) -> float:
    if not isinstance(position, (tuple, list)) or len(position) != 2:
        return 0.0
    x = int(position[0])
    y = int(position[1])
    if y < 0 or y >= len(grid) or x < 0 or x >= len(grid[y]):
        return 0.0
    cell = grid[y][x]
    return float(cell.get("entropy", shannon_entropy(float(cell.get("certainty", 0.5)))))


def build_monitor_state(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary", {})
    config = payload.get("config", {})
    grid = payload.get("grid", [])
    mesh_mode = "real"
    drones = []
    for drone in summary.get("drones", []):
        position = drone.get("position")
        drones.append(
            {
                "id": drone.get("id", "drone"),
                "alive": bool(drone.get("reachable", drone.get("alive", True))),
                "position": position,
                "target": drone.get("target"),
                "status": drone.get("status", "idle"),
                "current_entropy": _grid_entropy(grid, position),
            }
        )
    events = list(payload.get("events", []))[-8:]
    events.reverse()
    return {
        "elapsed": int(summary.get("duration_elapsed", 0)),
        "coverage": float(summary.get("coverage_current", summary.get("coverage", 0.0))) * 100,
        "avg_entropy": float(summary.get("average_entropy", 0.0)),
        "auctions": int(summary.get("auctions", 0)),
        "dropouts": int(summary.get("dropouts", 0)),
        "bft_rounds": int(summary.get("bft_rounds", 0)),
        "mesh": mesh_mode,
        "grid": grid,
        "drones": drones,
        "events": events,
        "target": list(config.get("target", summary.get("target", [7, 3]))),
        "survivor_found": bool(summary.get("survivor_found", False)),
    }


def main() -> int:
    args = parse_args()
    dashboard = TUIDashboard()
    sleep_seconds = max(args.interval_ms, 100) / 1000.0
    last_payload: dict[str, Any] | None = None
    last_change_at = time.monotonic()
    last_success_at = time.monotonic()
    survivor_started_at: float | None = None

    while True:
        try:
            payload = _fetch_json(args.source)
            last_success_at = time.monotonic()
        except (URLError, OSError, ConnectionResetError) as exc:
            snapshot_dir = Path("peer-runs")
            if snapshot_dir.exists() and any(snapshot_dir.glob("*.json")):
                payload = merge_peer_payloads(snapshot_dir)
                last_success_at = time.monotonic()
                if payload:
                    if payload != last_payload:
                        last_change_at = time.monotonic()
                        last_payload = payload
                    state = build_monitor_state(payload)
                    dashboard.render(state)
                    duration = int(payload.get("config", {}).get("duration", 0) or 0)
                    elapsed = int(state.get("elapsed", 0))
                    if duration and elapsed >= duration and (time.monotonic() - last_change_at) * 1000 >= args.idle_exit_ms:
                        break
                    time.sleep(sleep_seconds)
                    continue
            state = {
                "elapsed": 0,
                "coverage": 0,
                "avg_entropy": 0.0,
                "auctions": 0,
                "dropouts": 0,
                "bft_rounds": 0,
                "mesh": "real",
                "grid": [],
                "drones": [],
                "events": [{"t": 0, "type": "waiting", "message": f"monitor waiting for source: {exc}"}],
                "target": [7, 3],
            }
            dashboard.render(state)
            if last_payload is not None and (time.monotonic() - last_success_at) * 1000 >= args.idle_exit_ms:
                break
            time.sleep(sleep_seconds)
            continue

        if payload != last_payload:
            last_change_at = time.monotonic()
            last_payload = payload
        state = build_monitor_state(payload)
        if state.get("survivor_found"):
            survivor_started_at = survivor_started_at or time.monotonic()
            state["flash_target"] = int((time.monotonic() - survivor_started_at) / 0.25) % 2 == 0
        dashboard.render(state)

        duration = int(payload.get("config", {}).get("duration", 0) or 0)
        elapsed = int(state.get("elapsed", 0))
        if survivor_started_at is not None and (time.monotonic() - survivor_started_at) >= 5.0:
            break
        if duration and elapsed >= duration and (time.monotonic() - last_change_at) * 1000 >= args.idle_exit_ms:
            break
        time.sleep(sleep_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
