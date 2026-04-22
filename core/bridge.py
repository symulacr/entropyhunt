from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import threading
from typing import Any

logger = logging.getLogger("entropy_hunt.bridge")

_SAFE_ARG_RE: re.Pattern[str] = re.compile(r"^[\w./\-@:,=+]+$")

def _validate_arg(value: str, name: str) -> str:
    if name == "binary_path":
        resolved = shutil.which(value)
        if resolved is None:
            _msg = f"Binary not found: {value!r}"
            raise FileNotFoundError(_msg)
        return resolved
    if not _SAFE_ARG_RE.fullmatch(value):
        _msg = f"Unsafe argument rejected for {name}: {value!r}"
        raise ValueError(_msg)
    return value


class VertexBridge:
    __slots__ = (
        "_confirmed",
        "_last_stdout",
        "_lock",
        "_read_error",
        "_stderr_lines",
        "_stderr_lock",
        "binary_path",
        "confirm_markers",
        "keypair_path",
        "peer_addr",
        "proc",
    )

    def __init__(self, binary_path: str, keypair_path: str, peer_addr: str) -> None:
        self.binary_path = _validate_arg(binary_path, "binary_path")
        self.keypair_path = _validate_arg(keypair_path, "keypair_path")
        self.peer_addr = _validate_arg(peer_addr, "peer_addr")
        self.confirm_markers = tuple(
            marker.strip()
            for marker in os.environ.get(
                "ENTROPYHUNT_VERTEX_CONFIRM_MARKERS",
                "RECEIVED,received,[EVENT]",
            ).split(",")
            if marker.strip()
        )
        self.proc = subprocess.Popen(
            [self.binary_path, "--keypair", self.keypair_path, "--peer", self.peer_addr],
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
        self._stderr_lock = threading.Lock()
        self._read_error: str | None = None
        threading.Thread(target=self._read_loop, daemon=True).start()
        threading.Thread(target=self._read_stderr_loop, daemon=True).start()

    def _read_loop(self) -> None:
        try:
            if self.proc.stdout is None:
                self._read_error = "stdout stream is None"
                return
            for line in self.proc.stdout:
                try:
                    self._last_stdout = line.strip()
                    if any(marker in self._last_stdout for marker in self.confirm_markers):
                        self._confirmed.set()
                except Exception as exc:
                    self._read_error = f"stdout read loop crashed: {exc}"
                    logger.exception("VertexBridge stdout read loop crashed")
        except Exception as exc:
            self._read_error = f"stdout read loop crashed: {exc}"
            logger.exception("VertexBridge stdout read loop crashed")

    def _read_stderr_loop(self) -> None:
        try:
            if self.proc.stderr is None:
                with self._stderr_lock:
                    self._stderr_lines.append("[bridge-internal] stderr stream is None")
                return
            for line in self.proc.stderr:
                with self._stderr_lock:
                    self._stderr_lines.append(line.strip())
        except Exception as exc:
            with self._stderr_lock:
                self._stderr_lines.append(f"[bridge-internal] stderr read loop crashed: {exc}")
            logger.exception("VertexBridge stderr read loop crashed")

    def publish(self, topic: str, payload: dict[str, Any]) -> bool:
        if self._read_error is not None:
            return False
        msg = json.dumps({"topic": topic, "payload": payload}) + "\n"
        self._confirmed.clear()
        if self.proc.poll() is not None or self.proc.stdin is None:
            return False
        with self._lock:
            self.proc.stdin.write(msg)
            self.proc.stdin.flush()
        return self._confirmed.wait(timeout=2.0)

    def wait_confirmed(self, timeout: float = 2.0) -> bool:
        return self._confirmed.wait(timeout=timeout)

    def last_error(self) -> str:
        if self._read_error is not None:
            return self._read_error
        with self._stderr_lock:
            if self._stderr_lines:
                return self._stderr_lines[-1]
        return self._last_stdout

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
