from __future__ import annotations

import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any


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
        return {"summary": {"peer_count": 0}, "events": [], "grid": []}
    base = max(payloads, key=lambda item: int(item.get("summary", {}).get("duration_elapsed", 0)))
    drones: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []
    mesh_messages = 0
    bft_rounds = 0
    dropouts = 0
    survivor_receipts = 0
    for payload in payloads:
        summary = payload.get("summary", {})
        for drone in summary.get("drones", []):
            drones[str(drone.get("id"))] = drone
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
    merged_events = sorted(events, key=lambda event: (int(event.get("t", 0)), str(event.get("type", ""))))
    return {
        "summary": merged_summary,
        "events": merged_events,
        "grid": base.get("grid", []),
        "config": base.get("config", {}),
    }


class LiveRuntimeRequestHandler(BaseHTTPRequestHandler):
    snapshot_dir: Path

    def _write_json(self, payload: Any) -> None:
        encoded = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        merged = merge_peer_payloads(self.snapshot_dir)
        if self.path in {"/snapshot.json", "/snapshot"}:
            self._write_json(merged)
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
    snapshot_dir = Path(args.snapshot_dir)
    handler = partial(LiveRuntimeRequestHandler)
    handler.snapshot_dir = snapshot_dir  # type: ignore[attr-defined]
    server = ThreadingHTTPServer((args.host, args.port), handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
