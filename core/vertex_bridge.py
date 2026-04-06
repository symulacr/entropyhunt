from __future__ import annotations

import json
import os
import subprocess
import threading
from typing import Any


class VertexBridge:
    """Minimal stdin/stdout bridge to a running tashi-vertex helper process.

    The helper is expected to accept newline-delimited JSON on stdin and emit a
    confirmation line containing one of the configured confirmation markers on
    stdout when a payload has been received.
    """

    def __init__(self, binary_path: str, keypair_path: str, peer_addr: str) -> None:
        self.binary_path = binary_path
        self.keypair_path = keypair_path
        self.peer_addr = peer_addr
        self.confirm_markers = tuple(
            marker.strip()
            for marker in os.environ.get(
                "ENTROPYHUNT_VERTEX_CONFIRM_MARKERS",
                "RECEIVED,received,[EVENT]",
            ).split(",")
            if marker.strip()
        )
        self.proc = subprocess.Popen(
            [binary_path, "--keypair", keypair_path, "--peer", peer_addr],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._lock = threading.Lock()
        self._confirmed = threading.Event()
        self._last_stdout = ""
        self._stderr_lines: list[str] = []
        threading.Thread(target=self._read_loop, daemon=True).start()
        threading.Thread(target=self._read_stderr_loop, daemon=True).start()

    def _read_loop(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self._last_stdout = line.strip()
            if any(marker in self._last_stdout for marker in self.confirm_markers):
                self._confirmed.set()

    def _read_stderr_loop(self) -> None:
        assert self.proc.stderr is not None
        for line in self.proc.stderr:
            self._stderr_lines.append(line.strip())

    def publish(self, topic: str, payload: dict[str, Any]) -> bool:
        msg = json.dumps({"topic": topic, "payload": payload}) + "\n"
        self._confirmed.clear()
        if self.proc.poll() is not None or self.proc.stdin is None:
            return False
        with self._lock:
            self.proc.stdin.write(msg)
            self.proc.stdin.flush()
        return self._confirmed.wait(timeout=2.0)

    def last_error(self) -> str:
        if self._stderr_lines:
            return self._stderr_lines[-1]
        return self._last_stdout

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
