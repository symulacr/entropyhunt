from __future__ import annotations

import argparse
import atexit
import importlib
import json
import logging
import shutil
import signal
import sys
import time
from pathlib import Path
from typing import Any
from urllib.request import urlopen

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

shannon_entropy = importlib.import_module("core.certainty").shannon_entropy
TUIDashboard = importlib.import_module("dashboard.tui").TUIDashboard
merge_peer_payloads = importlib.import_module("scripts.serve_live_runtime").merge_peer_payloads


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor the live Entropy Hunt peer swarm in the terminal",
    )
    parser.add_argument("--source", default="http://127.0.0.1:8765/snapshot.json")
    parser.add_argument("--interval-ms", type=int, default=500)
    parser.add_argument("--idle-exit-ms", type=int, default=5000)
    return parser.parse_args()


_HTTP_TIMEOUT_SECONDS = 2.0
_HTTP_RETRY_COUNT = 2
MAX_EVENTS_DISPLAY = 8
_COORDINATE_DIMENSIONS = 2
_MAX_BACKOFF_SECONDS = 5.0


def _fetch_json(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=_HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _grid_entropy(
    grid: list[list[dict[str, Any]]],
    position: tuple[int, int] | list[int] | None,
) -> float:
    if not isinstance(position, (tuple, list)) or len(position) != _COORDINATE_DIMENSIONS:
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
    stats = payload.get("stats", {})
    mesh_info = payload.get("mesh", {})
    system = payload.get("system", {})
    mesh_mode = str(
        summary.get("mesh", mesh_info.get("transport", config.get("transport", "real"))),
    )
    drones = []
    for drone in summary.get("drones", []):
        position = drone.get("position")
        drones.append(
            {
                "id": drone.get("id", "drone"),
                "alive": bool(drone.get("alive", True)),
                "reachable": bool(drone.get("reachable", drone.get("alive", True))),
                "position": position,
                "target": drone.get("target"),
                "claimed_cell": drone.get("claimed_cell") or drone.get("claim_zone"),
                "status": drone.get("status", "idle"),
                "current_entropy": _grid_entropy(grid, position),
                "role": drone.get("role", "scout"),
                "subzone": drone.get("subzone"),
                "battery": float(drone.get("battery", -1.0)),
                "searched_cells": int(drone.get("searched_cells", 0)),
            },
        )
    events = list(payload.get("events", []))[-MAX_EVENTS_DISPLAY:]
    events.reverse()
    mesh_peers = list(summary.get("mesh_peers", []))
    pending_claims = list(summary.get("pending_claims", []))
    consensus_entries = list(summary.get("consensus", []))
    failures = list(summary.get("failures", []))
    last_consensus_result = None
    if consensus_entries:
        last_consensus_result = consensus_entries[-1].get("status")
    return {
        "elapsed": int(summary.get("duration_elapsed", 0)),
        "coverage": float(summary.get("coverage_current", summary.get("coverage", 0.0))) * 100,
        "coverage_completed": float(
            summary.get("coverage_completed", stats.get("coverage_completed", 0.0)),
        ),
        "coverage_visited": float(
            summary.get("coverage_visited", stats.get("coverage_visited", 0.0)),
        ),
        "avg_entropy": float(summary.get("average_entropy", 0.0)),
        "auctions": int(summary.get("auctions", 0)),
        "dropouts": int(summary.get("dropouts", 0)),
        "consensus_rounds": int(summary.get("consensus_rounds", 0)),
        "last_consensus_result": last_consensus_result,
        "mesh": mesh_mode,
        "mesh_peers": mesh_peers,
        "mesh_messages": int(summary.get("mesh_messages", mesh_info.get("messages", 0))),
        "pending_claims": pending_claims,
        "pending_claims_count": len(pending_claims),
        "consensus": consensus_entries,
        "consensus_count": len(consensus_entries),
        "failures": failures,
        "failure_count": len(failures),
        "grid": grid,
        "drones": drones,
        "events": events,
        "target": list(config.get("target", summary.get("target", [7, 3]))),
        "survivor_found": bool(summary.get("survivor_found", False)),
        "survivor_receipts": int(summary.get("survivor_receipts", 0)),
        "tick_seconds": system.get("tick_seconds", summary.get("tick_seconds")),
        "tick_delay_seconds": system.get("tick_delay_seconds", summary.get("tick_delay_seconds")),
        "peer_count": int(summary.get("peer_count", mesh_info.get("peer_count", len(mesh_peers)))),
        "requested_drone_count": system.get("requested_drone_count", config.get("requested_drone_count")),
        "stats": stats,
        "mesh_info": mesh_info,
        "system_info": system,
    }


def _restore_terminal() -> None:
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()


def _setup_keyboard() -> Any:
    try:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        return old_settings
    except Exception:
        return None


def _restore_keyboard(old_settings: Any) -> None:
    try:
        import termios
        fd = sys.stdin.fileno()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except Exception:
        pass


def _read_key() -> str | None:
    try:
        import select
        if select.select([sys.stdin], [], [], 0)[0]:
            ch = sys.stdin.read(1)
            if not ch:
                return None
            if ch == "\x1b":
                if select.select([sys.stdin], [], [], 0.05)[0]:
                    ch2 = sys.stdin.read(1)
                    if ch2 == "[" and select.select([sys.stdin], [], [], 0.05)[0]:
                        ch3 = sys.stdin.read(1)
                        if ch3 in ("A", "B", "C", "D"):
                            return None
                return "\x1b"
            return ch
    except Exception:
        pass
    return None


def _build_debug_dict(
    last_fetch_latency_ms: float,
    last_render_latency_ms: float,
    state: dict[str, Any],
    last_error: str | None,
) -> dict[str, Any]:
    return {
        "fetch_latency_ms": round(last_fetch_latency_ms, 2),
        "render_latency_ms": round(last_render_latency_ms, 2),
        "state_key_count": len(state),
        "last_error": last_error or "",
    }


def _render_state(
    dashboard: Any,
    state: dict[str, Any],
    last_render_latency_ms: float,
) -> float:
    render_start = time.monotonic()
    dashboard.render(state)
    return (time.monotonic() - render_start) * 1000


def main() -> int:
    args = parse_args()
    dashboard = TUIDashboard()
    sleep_seconds = max(args.interval_ms, 100) / 1000.0
    last_payload: dict[str, Any] | None = None
    last_change_at = time.monotonic()
    last_success_at = time.monotonic()
    survivor_started_at: float | None = None
    last_known_state: dict[str, Any] | None = None
    _shutdown_requested = False
    _paused = False
    _step_once = False
    _force_refresh = False
    debug_mode = False

    frame_counter = 0
    paused_frame_counter = 0

    seen_event_keys: set[str] = set()
    was_stale = False
    transition_flash_frames = 0
    survivor_flash_frames = 0
    _survivor_found_previously = False

    retry_count = 0
    _next_fetch_at = 0.0
    last_fetch_latency_ms = 0.0
    last_render_latency_ms = 0.0
    last_error: str | None = None

    last_term_size = shutil.get_terminal_size()
    waiting_dots = 0

    def _signal_handler(signum: int, _frame: Any) -> None:
        nonlocal _shutdown_requested
        _shutdown_requested = True
        logger.warning("Received %s, initiating graceful shutdown...", signal.Signals(signum).name)
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    atexit.register(_restore_terminal)
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    old_settings = _setup_keyboard()
    if old_settings is not None:
        atexit.register(lambda: _restore_keyboard(old_settings))

    try:
        while True:
            if _shutdown_requested:
                break

            key = _read_key()
            if key is not None:
                if key.lower() == "q" or key == "\x1b":
                    _shutdown_requested = True
                    break
                elif key.lower() == "p":
                    _paused = not _paused
                    if _paused:
                        paused_frame_counter = frame_counter
                        frame_counter = 0
                    else:
                        frame_counter = paused_frame_counter
                elif key.lower() == "s" and _paused:
                    _step_once = True
                elif key == "\x03":
                    _shutdown_requested = True
                    break
                elif key.lower() == "r":
                    _force_refresh = True
                    _next_fetch_at = 0
                    retry_count = 0
                elif key in ("+", "="):
                    sleep_seconds = max(sleep_seconds - 0.1, 0.1)
                elif key in ("-", "_"):
                    sleep_seconds = min(sleep_seconds + 0.1, 10.0)
                elif key.lower() == "d":
                    debug_mode = not debug_mode

            current_term_size = shutil.get_terminal_size()
            terminal_size_changed = False
            if current_term_size != last_term_size:
                last_term_size = current_term_size
                terminal_size_changed = True

            if _paused and not _step_once:
                if last_known_state is not None:
                    state = dict(last_known_state)
                    state["paused"] = True
                    state["frame_counter"] = frame_counter
                    state["terminal_size_changed"] = terminal_size_changed
                    if debug_mode:
                        state["debug"] = _build_debug_dict(
                            last_fetch_latency_ms,
                            last_render_latency_ms,
                            state,
                            last_error,
                        )
                    try:
                        last_render_latency_ms = _render_state(dashboard, state, last_render_latency_ms)
                        if not _paused:
                            frame_counter += 1
                    except Exception as render_exc:
                        logger.warning("Render failed: %s", render_exc)
                time.sleep(sleep_seconds)
                continue
            _step_once = False

            now = time.monotonic()
            if not _force_refresh and now < _next_fetch_at:
                if last_known_state is not None:
                    stale_seconds = int(now - last_success_at)
                    state = dict(last_known_state)
                    state["stale_message"] = f"STALE {stale_seconds}s (retry {retry_count})"
                else:
                    waiting_dots = (waiting_dots + 1) % 4
                    dots = "." * waiting_dots
                    state = {
                        "elapsed": 0,
                        "coverage": 0,
                        "coverage_completed": 0.0,
                        "coverage_visited": 0.0,
                        "avg_entropy": 0.0,
                        "auctions": 0,
                        "dropouts": 0,
                        "consensus_rounds": 0,
                        "last_consensus_result": None,
                        "mesh": "real",
                        "mesh_peers": [],
                        "mesh_messages": 0,
                        "pending_claims": [],
                        "pending_claims_count": 0,
                        "consensus": [],
                        "consensus_count": 0,
                        "failures": [],
                        "failure_count": 0,
                        "grid": [],
                        "drones": [],
                        "events": [
                            {"t": 0, "type": "waiting", "message": f"monitor waiting{dots}"},
                        ],
                        "target": [7, 3],
                        "survivor_found": False,
                        "survivor_receipts": 0,
                        "tick_seconds": None,
                        "tick_delay_seconds": None,
                        "peer_count": 0,
                        "requested_drone_count": None,
                        "stats": {},
                        "mesh_info": {},
                        "system_info": {},
                        "stale_message": f"WAITING (retry {retry_count})",
                    }
                state["frame_counter"] = frame_counter
                state["terminal_size_changed"] = terminal_size_changed
                was_stale = True
                if debug_mode:
                    state["debug"] = _build_debug_dict(
                        last_fetch_latency_ms,
                        last_render_latency_ms,
                        state,
                        last_error,
                    )
                try:
                    last_render_latency_ms = _render_state(dashboard, state, last_render_latency_ms)
                    frame_counter += 1
                except Exception as render_exc:
                    logger.warning("Render failed: %s", render_exc)
                time.sleep(min(sleep_seconds, _next_fetch_at - now + 0.01))
                continue

            _force_refresh = False
            fetch_start = time.monotonic()
            payload: dict[str, Any] | None = None
            try:
                payload = _fetch_json(args.source)
                last_success_at = time.monotonic()
                last_fetch_latency_ms = (last_success_at - fetch_start) * 1000
                retry_count = 0
                _next_fetch_at = 0
            except Exception as exc:
                logger.warning("Fetch failed: %s", exc)
                retry_count += 1
                backoff = min(0.5 * (2 ** (retry_count - 1)), _MAX_BACKOFF_SECONDS)
                _next_fetch_at = time.monotonic() + backoff
                last_error = str(exc)
                last_fetch_latency_ms = (time.monotonic() - fetch_start) * 1000

                snapshot_dir = Path("peer-runs")
                if snapshot_dir.exists() and any(snapshot_dir.glob("*.json")):
                    try:
                        payload = merge_peer_payloads(snapshot_dir)
                        last_success_at = time.monotonic()
                        retry_count = 0
                        _next_fetch_at = 0
                    except Exception as fallback_exc:
                        logger.warning("Peer-runs fallback failed: %s", fallback_exc)
                        last_error = str(fallback_exc)

            if payload is None:
                if last_known_state is not None:
                    stale_seconds = int(time.monotonic() - last_success_at)
                    state = dict(last_known_state)
                    state["stale_message"] = f"STALE {stale_seconds}s (retry {retry_count})"
                else:
                    waiting_dots = (waiting_dots + 1) % 4
                    dots = "." * waiting_dots
                    state = {
                        "elapsed": 0,
                        "coverage": 0,
                        "coverage_completed": 0.0,
                        "coverage_visited": 0.0,
                        "avg_entropy": 0.0,
                        "auctions": 0,
                        "dropouts": 0,
                        "consensus_rounds": 0,
                        "last_consensus_result": None,
                        "mesh": "real",
                        "mesh_peers": [],
                        "mesh_messages": 0,
                        "pending_claims": [],
                        "pending_claims_count": 0,
                        "consensus": [],
                        "consensus_count": 0,
                        "failures": [],
                        "failure_count": 0,
                        "grid": [],
                        "drones": [],
                        "events": [
                            {"t": 0, "type": "waiting", "message": f"monitor waiting{dots}"},
                        ],
                        "target": [7, 3],
                        "survivor_found": False,
                        "survivor_receipts": 0,
                        "tick_seconds": None,
                        "tick_delay_seconds": None,
                        "peer_count": 0,
                        "requested_drone_count": None,
                        "stats": {},
                        "mesh_info": {},
                        "system_info": {},
                        "stale_message": f"WAITING (retry {retry_count})",
                    }
                state["frame_counter"] = frame_counter
                state["terminal_size_changed"] = terminal_size_changed
                was_stale = True
                if debug_mode:
                    state["debug"] = _build_debug_dict(
                        last_fetch_latency_ms,
                        last_render_latency_ms,
                        state,
                        last_error,
                    )
                try:
                    last_render_latency_ms = _render_state(dashboard, state, last_render_latency_ms)
                    frame_counter += 1
                except Exception as render_exc:
                    logger.warning("Render failed: %s", render_exc)
                if (
                    last_payload is not None
                    and (time.monotonic() - last_success_at) * 1000 >= args.idle_exit_ms
                ):
                    break
                time.sleep(sleep_seconds)
                continue

            if payload != last_payload:
                last_change_at = time.monotonic()
                last_payload = payload
            state = build_monitor_state(payload)
            last_known_state = state

            events = state.get("events", [])
            new_event_hashes: list[str] = []
            for event in events:
                ev_key = str(event.get("t", 0)) + str(event.get("message", ""))
                if ev_key not in seen_event_keys:
                    seen_event_keys.add(ev_key)
                    new_event_hashes.append(ev_key)
            state["new_event_ids"] = new_event_hashes

            if was_stale:
                transition_flash_frames = 2
                was_stale = False
            if transition_flash_frames > 0:
                state["transition_flash"] = True
                transition_flash_frames -= 1
            else:
                state["transition_flash"] = False

            if state.get("survivor_found"):
                if not _survivor_found_previously:
                    survivor_flash_frames = 10
                    _survivor_found_previously = True
                survivor_started_at = survivor_started_at or time.monotonic()
                state["flash_target"] = int((time.monotonic() - survivor_started_at) / 0.25) % 2 == 0
            else:
                _survivor_found_previously = False
                survivor_started_at = None

            if survivor_flash_frames > 0:
                state["survivor_flash_frames"] = survivor_flash_frames
                survivor_flash_frames -= 1
            else:
                state["survivor_flash_frames"] = 0

            state["frame_counter"] = frame_counter
            state["terminal_size_changed"] = terminal_size_changed

            if debug_mode:
                state["debug"] = _build_debug_dict(
                    last_fetch_latency_ms,
                    last_render_latency_ms,
                    state,
                    last_error,
                )

            try:
                last_render_latency_ms = _render_state(dashboard, state, last_render_latency_ms)
                frame_counter += 1
            except Exception as render_exc:
                logger.warning("Render failed: %s", render_exc)

            duration = int(payload.get("config", {}).get("duration", 0) or 0)
            elapsed = int(state.get("elapsed", 0))
            _survivor_display_seconds = 5.0
            if (
                survivor_started_at is not None
                and (time.monotonic() - survivor_started_at) >= _survivor_display_seconds
            ):
                break
            if (
                duration
                and elapsed >= duration
                and (time.monotonic() - last_change_at) * 1000 >= args.idle_exit_ms
            ):
                break
            time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        logger.info("Shutdown requested.")
    finally:
        _restore_terminal()
        if old_settings is not None:
            _restore_keyboard(old_settings)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
