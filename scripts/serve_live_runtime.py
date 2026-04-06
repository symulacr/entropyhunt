from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import time
from typing import Any, cast


CONTROL_KEYS = {"tick_seconds", "tick_delay_seconds", "requested_drone_count"}


def load_control_payload(control_path: Path) -> dict[str, Any]:
    if not control_path.exists():
        return {}
    try:
        payload = json.loads(control_path.read_text())
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_peer_payloads(snapshot_dir: Path) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for path in sorted(snapshot_dir.glob("*.json")):
        try:
            payloads.append(json.loads(path.read_text()))
        except json.JSONDecodeError:
            continue
    return payloads


def merge_peer_payloads(snapshot_dir: Path) -> dict[str, Any]:
    payloads = load_peer_payloads(snapshot_dir)
    if not payloads:
        return {"summary": {"peer_count": 0}, "events": [], "grid": [], "config": {}}

    base = max(payloads, key=lambda item: int(item.get("summary", {}).get("duration_elapsed", 0)))
    drones: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []
    mesh_messages = 0
    bft_rounds = 0
    dropouts = 0
    survivor_receipts = 0
    control = load_control_payload(snapshot_dir / "control.json")

    for payload in payloads:
        summary = payload.get("summary", {})
        for drone in summary.get("drones", []):
            drones[str(drone.get("id", ""))] = drone
        events.extend(payload.get("events", []))
        mesh_messages += int(summary.get("mesh_messages", 0))
        bft_rounds = max(bft_rounds, int(summary.get("bft_rounds", 0)))
        dropouts = max(dropouts, int(summary.get("dropouts", 0)))
        survivor_receipts = max(survivor_receipts, int(summary.get("survivor_receipts", 0)))

    merged_summary = dict(base.get("summary", {}))
    merged_summary["peer_count"] = len(payloads)
    merged_summary["mesh_messages"] = mesh_messages
    merged_summary["bft_rounds"] = bft_rounds
    merged_summary["dropouts"] = dropouts
    merged_summary["survivor_receipts"] = survivor_receipts
    merged_summary["drones"] = sorted(drones.values(), key=lambda drone: str(drone.get("id", "")))
    merged_summary["mesh"] = str(base.get("summary", {}).get("mesh", base.get("config", {}).get("transport", "local")))

    deduped_events: list[dict[str, Any]] = []
    seen_event_keys: set[tuple[object, object, object, object]] = set()
    for event in sorted(events, key=lambda event: (int(event.get("t", 0)), str(event.get("type", "")))):
        key = (
            event.get("contest_id"),
            event.get("type"),
            event.get("message"),
            int(event.get("t", 0)),
        )
        if key in seen_event_keys:
            continue
        seen_event_keys.add(key)
        deduped_events.append(event)
    grid_size = int(base.get("config", {}).get("grid", len(base.get("grid", []))))
    merged_grid = base.get("grid", [])
    if grid_size and payloads:
        merged_grid = []
        for y in range(grid_size):
            row: list[dict[str, Any]] = []
            for x in range(grid_size):
                best_cell: dict[str, Any] | None = None
                best_certainty = -1.0
                for payload in payloads:
                    grid = payload.get("grid", [])
                    if y >= len(grid) or x >= len(grid[y]):
                        continue
                    cell = dict(grid[y][x])
                    certainty = float(cell.get("certainty", 0.5))
                    if certainty > best_certainty:
                        best_certainty = certainty
                        best_cell = cell
                row.append(best_cell or {"x": x, "y": y, "certainty": 0.5, "entropy": 1.0})
            merged_grid.append(row)
    merged_config = dict(base.get("config", {}))
    merged_config.update(control)
    if "requested_drone_count" not in merged_config:
        merged_config["requested_drone_count"] = merged_config.get("drone_count", len(payloads))
    merged_config["control_url"] = "/control"
    merged_config["control_capabilities"] = {
        "tick_seconds": "live",
        "tick_delay_seconds": "live",
        "requested_drone_count": "next_run",
    }
    return {
        "summary": merged_summary,
        "events": deduped_events,
        "grid": merged_grid,
        "config": merged_config,
    }


class SnapshotHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler], *, snapshot_dir: Path) -> None:
        super().__init__(server_address, handler_class)
        self.snapshot_dir = snapshot_dir
        self.control_path = snapshot_dir / "control.json"


class LiveRuntimeRequestHandler(BaseHTTPRequestHandler):
    def _write_json(self, payload: Any) -> None:
        encoded = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        snapshot_dir = cast(SnapshotHTTPServer, self.server).snapshot_dir
        merged = merge_peer_payloads(snapshot_dir)
        if self.path in {"/snapshot.json", "/snapshot"}:
            self._write_json(merged)
            return
        if self.path in {"/control.json", "/control"}:
            self._write_json(load_control_payload(cast(SnapshotHTTPServer, self.server).control_path))
            return
        if self.path in {"/state.json", "/state"}:
            self._write_json(merged["summary"])
            return
        if self.path in {"/events.json", "/events"}:
            self._write_json(merged["events"])
            return
        self.send_response(404)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in {"/control.json", "/control"}:
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return
        if not isinstance(payload, dict):
            self.send_response(400)
            self.end_headers()
            return
        current = load_control_payload(cast(SnapshotHTTPServer, self.server).control_path)
        for key, value in payload.items():
            if key not in CONTROL_KEYS:
                continue
            if key in {"tick_seconds", "requested_drone_count"} and isinstance(value, int) and value > 0:
                current[key] = value
            elif key == "tick_delay_seconds" and isinstance(value, (int, float)):
                current[key] = max(0.0, float(value))
        current["updated_at_ms"] = int(time.time() * 1000)
        cast(SnapshotHTTPServer, self.server).control_path.write_text(json.dumps(current, indent=2))
        self._write_json(current)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve live peer snapshots over HTTP")
    parser.add_argument("--snapshot-dir", default="peer-runs")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = SnapshotHTTPServer(
        (args.host, args.port),
        LiveRuntimeRequestHandler,
        snapshot_dir=Path(args.snapshot_dir),
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
