from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import logging
import os
import select
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

CONTROL_KEYS = {"tick_seconds", "tick_delay_seconds", "requested_drone_count"}
SnapshotSignature = tuple[tuple[str, int, int], ...]

_snapshot_cache: dict[str, Any] = {}
_snapshot_cache_time: float = 0.0
_CACHE_TTL = 1.0

_ALLOWED_ORIGIN = os.environ.get("ENTROPYHUNT_ALLOWED_ORIGIN", "localhost")


def _require_secret() -> bytes:
    raw = os.environ.get("ENTROPYHUNT_MESH_SECRET", "")
    if not raw:
        raise OSError("ENTROPYHUNT_MESH_SECRET must be set and non-empty")
    return raw.encode()


def get_cached_snapshot(snapshot_dir: Path) -> dict[str, Any]:
    global _snapshot_cache, _snapshot_cache_time
    now = time.monotonic()
    if now - _snapshot_cache_time < _CACHE_TTL and _snapshot_cache:
        return _snapshot_cache
    _snapshot_cache = merge_peer_payloads(snapshot_dir)
    _snapshot_cache_time = now
    return _snapshot_cache


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
        if path.name == "control.json":
            continue
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            continue
        payloads.append(payload)
    return payloads


def merge_peer_payloads(snapshot_dir: Path) -> dict[str, Any]:
    control = load_control_payload(snapshot_dir / "control.json")
    payloads = load_peer_payloads(snapshot_dir)
    if not payloads:
        return {
            "summary": {"peer_count": 0, "drones": []},
            "events": [],
            "grid": [],
            "config": {
                **control,
                "source_mode": "peer-merged-live",
                "snapshot_provenance": "control-only-placeholder",
                "synthetic": True,
                "control_url": "/control",
                "control_capabilities": {
                    "tick_seconds": "live",
                    "tick_delay_seconds": "live",
                    "requested_drone_count": "next_run",
                },
            },
        }

    base = max(payloads, key=lambda item: int(item.get("summary", {}).get("duration_elapsed", 0)))
    drones: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []
    mesh_messages = 0
    consensus_rounds = 0
    dropouts = 0
    survivor_receipts = 0
    mesh_peers: dict[str, dict[str, Any]] = {}
    pending_claims: dict[str, dict[str, Any]] = {}
    consensus_entries: dict[str, dict[str, Any]] = {}
    failure_entries: dict[tuple[str, int], dict[str, Any]] = {}
    for payload in payloads:
        summary = payload.get("summary", {})
        for drone in summary.get("drones", []):
            drones[str(drone.get("id", ""))] = drone
        events.extend(payload.get("events", []))
        mesh_messages += int(summary.get("mesh_messages", 0))
        consensus_rounds = max(consensus_rounds, int(summary.get("consensus_rounds", 0)))
        dropouts = max(dropouts, int(summary.get("dropouts", 0)))
        survivor_receipts = max(survivor_receipts, int(summary.get("survivor_receipts", 0)))
        for peer in summary.get("mesh_peers", []):
            peer_id = str(peer.get("peer_id", ""))
            if not peer_id:
                continue
            existing = mesh_peers.get(peer_id)
            if existing is None or int(peer.get("last_seen_ms", 0)) > int(existing.get("last_seen_ms", 0)):
                mesh_peers[peer_id] = dict(peer)
            elif existing is not None and peer.get("stale"):
                existing["stale"] = True
        for claim in summary.get("pending_claims", []):
            claim_id = str(claim.get("claim_id", ""))
            if claim_id:
                pending_claims[claim_id] = dict(claim)
        for entry in summary.get("consensus", []):
            contest_id = str(entry.get("contest_id", ""))
            if contest_id:
                consensus_entries[contest_id] = dict(entry)
        for failure in summary.get("failures", []):
            key = (str(failure.get("drone_id", "")), int(failure.get("t", 0)))
            if key not in failure_entries:
                failure_entries[key] = dict(failure)

    merged_summary = dict(base.get("summary", {}))
    merged_summary["peer_count"] = len(payloads)
    merged_summary["mesh_messages"] = mesh_messages
    merged_summary["consensus_rounds"] = consensus_rounds
    merged_summary["dropouts"] = dropouts
    merged_summary["survivor_receipts"] = survivor_receipts
    merged_summary["drones"] = sorted(drones.values(), key=lambda drone: str(drone.get("id", "")))
    merged_summary["mesh"] = str(
        base.get("summary", {}).get("mesh", base.get("config", {}).get("transport", "local")),
    )
    merged_summary["mesh_peers"] = sorted(mesh_peers.values(), key=lambda p: str(p.get("peer_id", "")))
    merged_summary["pending_claims"] = sorted(pending_claims.values(), key=lambda c: int(c.get("timestamp_ms", 0)))
    merged_summary["consensus"] = sorted(consensus_entries.values(), key=lambda r: int(r.get("round_id", 0)))
    merged_summary["failures"] = sorted(failure_entries.values(), key=lambda f: (int(f.get("t", 0)), str(f.get("drone_id", ""))))

    deduped_events: list[dict[str, Any]] = []
    seen_event_keys: set[tuple[object, object, object, object]] = set()
    for event in sorted(
        events,
        key=lambda event: (int(event.get("t", 0)), str(event.get("type", ""))),
    ):
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
                best_last_updated_ms = -1
                for payload in payloads:
                    grid = payload.get("grid", [])
                    if y >= len(grid) or x >= len(grid[y]):
                        continue
                    cell = dict(grid[y][x])
                    certainty = float(cell.get("certainty", 0.5))
                    last_updated_ms = int(cell.get("last_updated_ms", 0))
                    if last_updated_ms > best_last_updated_ms or (
                        last_updated_ms == best_last_updated_ms and certainty > best_certainty
                    ):
                        best_certainty = certainty
                        best_last_updated_ms = last_updated_ms
                        best_cell = cell
                row.append(best_cell or {"x": x, "y": y, "certainty": 0.5, "entropy": 1.0})
            merged_grid.append(row)
    merged_config = dict(base.get("config", {}))
    merged_config.update(control)
    if "requested_drone_count" not in merged_config:
        merged_config["requested_drone_count"] = merged_config.get("drone_count", len(payloads))
    merged_config["source_mode"] = "peer-merged-live"
    merged_config["snapshot_provenance"] = "merged-live"
    merged_config["synthetic"] = False
    merged_config["control_url"] = "/control"
    merged_config["control_capabilities"] = {
        "tick_seconds": "live",
        "tick_delay_seconds": "live",
        "requested_drone_count": "next_run",
    }

    live_drones = [d for d in merged_summary.get("drones", []) if d.get("alive") is not False and d.get("reachable") is not False]
    stale_peers = [p for p in merged_summary.get("mesh_peers", []) if p.get("stale")]
    stats = {
        "coverage": merged_summary.get("coverage_current", merged_summary.get("coverage", 0)),
        "coverage_completed": merged_summary.get("coverage_completed", 0),
        "coverage_visited": merged_summary.get("coverage_visited", 0),
        "average_entropy": merged_summary.get("average_entropy", 0),
        "auctions": merged_summary.get("auctions", 0),
        "consensus_rounds": merged_summary.get("consensus_rounds", 0),
        "dropouts": merged_summary.get("dropouts", 0),
        "survivor_found": merged_summary.get("survivor_found", False),
        "survivor_receipts": merged_summary.get("survivor_receipts", 0),
        "mesh_messages": merged_summary.get("mesh_messages", 0),
        "duration_elapsed": merged_summary.get("duration_elapsed", 0),
        "drones_total": len(merged_summary.get("drones", [])),
        "drones_live": len(live_drones),
        "peers_total": len(merged_summary.get("mesh_peers", [])),
        "peers_stale": len(stale_peers),
        "pending_claims": len(merged_summary.get("pending_claims", [])),
        "consensus_count": len(merged_summary.get("consensus", [])),
        "failure_count": len(merged_summary.get("failures", [])),
    }
    mesh = {
        "transport": merged_summary.get("mesh", merged_config.get("transport", "local")),
        "peer_count": merged_summary.get("peer_count", 0),
        "peers": merged_summary.get("mesh_peers", []),
        "messages": merged_summary.get("mesh_messages", 0),
    }
    system = {
        "tick_seconds": merged_summary.get("tick_seconds", 1),
        "tick_delay_seconds": merged_summary.get("tick_delay_seconds", 0.1),
        "requested_drone_count": merged_summary.get("requested_drone_count", len(payloads)),
        "target": merged_summary.get("target", [0, 0]),
    }
    return {
        "summary": merged_summary,
        "stats": stats,
        "mesh": mesh,
        "system": system,
        "events": deduped_events,
        "grid": merged_grid,
        "config": merged_config,
    }


class SnapshotHTTPServer(ThreadingHTTPServer):
    __slots__ = ("_merged_cache", "_merged_signature", "control_path", "snapshot_dir")
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        snapshot_dir: Path,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.snapshot_dir = snapshot_dir
        self.control_path = snapshot_dir / "control.json"
        self._merged_cache: dict[str, Any] | None = None
        self._merged_signature: SnapshotSignature | None = None

    def snapshot_signature(self) -> SnapshotSignature:
        return self._snapshot_signature()

    def _snapshot_signature(self) -> SnapshotSignature:
        entries: list[tuple[str, int, int]] = []
        for path in sorted(self.snapshot_dir.glob("*.json")):
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            entries.append((path.name, stat.st_mtime_ns, stat.st_size))
        return tuple(entries)

    def get_merged_payload(self) -> dict[str, Any]:
        signature = self._snapshot_signature()
        if self._merged_cache is None or signature != self._merged_signature:
            self._merged_cache = merge_peer_payloads(self.snapshot_dir)
            self._merged_signature = signature
        return self._merged_cache


class LiveRuntimeRequestHandler(BaseHTTPRequestHandler):
    __slots__ = ()

    def _write_json(self, payload: object) -> None:
        encoded = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", _ALLOWED_ORIGIN)
        self.end_headers()
        self.wfile.write(encoded)

    def _write_sse_event(self, event: str, data: object) -> None:
        payload = json.dumps(data, separators=(",", ":"))
        self.wfile.write(f"event: {event}\ndata: {payload}\n\n".encode())
        self.wfile.flush()

    def _handle_sse_stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", _ALLOWED_ORIGIN)
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        server = cast("SnapshotHTTPServer", self.server)
        self._write_sse_event("snapshot", server.get_merged_payload())

        stop_event = threading.Event()

        def _poll_loop() -> None:
            last_sig = server.snapshot_signature()
            while not stop_event.is_set():
                time.sleep(0.5)
                try:
                    sig = server.snapshot_signature()
                    if sig != last_sig:
                        last_sig = sig
                        self._write_sse_event("snapshot", server.get_merged_payload())
                except (OSError, ValueError, ConnectionError):
                    break

        poll_thread = threading.Thread(target=_poll_loop, daemon=True)
        poll_thread.start()
        try:
            socket_obj = self.request
            socket_obj.settimeout(5.0)
            while not stop_event.is_set():
                try:
                    readable, _, _ = select.select([socket_obj], [], [], 5.0)
                    if readable:
                        chunk = self.rfile.read(1)
                        if not chunk:
                            break
                except (OSError, ValueError):
                    break
        finally:
            stop_event.set()
            poll_thread.join(timeout=2.0)

    def do_GET(self) -> None:
        if self.path in {"/control.json", "/control"}:
            self._write_json(
                load_control_payload(cast("SnapshotHTTPServer", self.server).control_path),
            )
            return
        if self.path in {"/stream", "/events/stream"}:
            self._handle_sse_stream()
            return
        merged = cast("SnapshotHTTPServer", self.server).get_merged_payload()
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
        self.send_header("Access-Control-Allow-Origin", _ALLOWED_ORIGIN)
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", _ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:
        if self.path not in {"/control.json", "/control"}:
            self.send_response(404)
            self.end_headers()
            return
        origin = self.headers.get("Origin", "")
        if origin and _ALLOWED_ORIGIN not in origin:
            self.send_response(403)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        secret = _require_secret()
        if secret:
            token = self.headers.get("X-Auth-Token")
            if not token:
                self.send_response(401)
                self.end_headers()
                return
            expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(token, expected):
                self.send_response(403)
                self.end_headers()
                return
        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return
        if not isinstance(payload, dict):
            self.send_response(400)
            self.end_headers()
            return
        current = load_control_payload(cast("SnapshotHTTPServer", self.server).control_path)
        for key, value in payload.items():
            if key not in CONTROL_KEYS:
                continue
            if (
                key in {"tick_seconds", "requested_drone_count"}
                and isinstance(value, int)
                and value > 0
            ):
                current[key] = value
            elif key == "tick_delay_seconds" and isinstance(value, (int, float)):
                current[key] = max(0.0, float(value))
        current["updated_at_ms"] = int(time.time() * 1000)
        cast("SnapshotHTTPServer", self.server).control_path.write_text(
            json.dumps(current, indent=2),
        )
        self._write_json(current)

    def log_message(self, format: str, *args: object) -> None:
        return


def _start_ws_server(host: str, port: int, snapshot_dir: Path) -> None:
    try:
        import websockets
    except ImportError:
        return

    async def _handler(websocket: Any) -> None:
        try:
            while True:
                payload = get_cached_snapshot(snapshot_dir)
                await websocket.send(json.dumps(payload))
                await asyncio.sleep(2.0)
        except Exception as exc:
            logging.debug("WebSocket client disconnected: %s", exc)

    async def _serve() -> None:
        async with websockets.serve(_handler, host, port):
            await asyncio.Future()

    asyncio.run(_serve())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve live peer snapshots over HTTP")
    parser.add_argument("--snapshot-dir", default="peer-runs")
    parser.add_argument("--host", default=os.environ.get("ENTROPYHUNT_SERVE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--ws-port", type=int, default=8766)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot_dir = Path(args.snapshot_dir)
    ws_thread = threading.Thread(
        target=_start_ws_server,
        args=(args.host, args.ws_port, snapshot_dir),
        daemon=True,
    )
    ws_thread.start()
    server = SnapshotHTTPServer(
        (args.host, args.port),
        LiveRuntimeRequestHandler,
        snapshot_dir=snapshot_dir,
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
