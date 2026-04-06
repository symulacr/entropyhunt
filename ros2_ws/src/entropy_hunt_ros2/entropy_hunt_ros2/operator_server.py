from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any


class _SnapshotHandler(BaseHTTPRequestHandler):
    snapshot_supplier: Any = None
    control_supplier: Any = None
    control_updater: Any = None

    def _write_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/snapshot.json":
            payload = self.snapshot_supplier() if self.snapshot_supplier is not None else {}
            self._write_json(payload)
            return
        if self.path == "/control":
            payload = self.control_supplier() if self.control_supplier is not None else {}
            self._write_json(payload)
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
        if self.path != "/control":
            self.send_response(404)
            self.end_headers()
            return
        if self.control_updater is None:
            self._write_json({"error": "ROS operator control is read-only in this lane"}, status=405)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._write_json({"error": "invalid JSON"}, status=400)
            return
        if not isinstance(payload, dict):
            self._write_json({"error": "control payload must be an object"}, status=400)
            return
        self._write_json(self.control_updater(payload))

    def log_message(self, _format: str, *_args: object) -> None:
        return None


class OperatorSnapshotServer:
    def __init__(
        self,
        host: str,
        port: int,
        snapshot_supplier: Any,
        control_supplier: Any | None = None,
        control_updater: Any | None = None,
    ) -> None:
        _SnapshotHandler.snapshot_supplier = staticmethod(snapshot_supplier)
        _SnapshotHandler.control_supplier = staticmethod(control_supplier) if control_supplier is not None else None
        _SnapshotHandler.control_updater = staticmethod(control_updater) if control_updater is not None else None
        self._server = HTTPServer((host, port), _SnapshotHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=1.0)


def write_snapshot_file(snapshot_path: str, payload: dict[str, Any]) -> None:
    if not snapshot_path:
        return
    path = Path(snapshot_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
