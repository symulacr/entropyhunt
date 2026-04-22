from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any

from simulation.proof import ProofLogger

if TYPE_CHECKING:
    import types
    from collections.abc import Sequence

ROOT = Path(__file__).resolve().parent.parent

FAILOVER_EVENT_TYPES = {"failure", "heartbeat_timeout", "stale", "survivor", "survivor_found"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a local multi-peer Entropy Hunt demo")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--base-port", type=int, default=9101)
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--grid", type=int, default=10)
    parser.add_argument("--tick-seconds", type=int, default=1)
    parser.add_argument("--tick-delay-seconds", type=float, default=None)
    parser.add_argument("--target", default="7,3")
    parser.add_argument("--fail", dest="fail_drone", default="drone_2")
    parser.add_argument("--fail-at", type=int, default=60)
    parser.add_argument("--output-dir", default="peer-runs")
    parser.add_argument("--transport", choices=("local", "foxmq"), default="local")
    parser.add_argument("--mqtt-host", default=os.environ.get("ENTROPYHUNT_MQTT_HOST", "127.0.0.1"))
    parser.add_argument("--mqtt-base-port", type=int, default=1884)
    parser.add_argument(
        "--serve-host",
        default=os.environ.get("ENTROPYHUNT_SERVE_HOST", "127.0.0.1"),
    )
    parser.add_argument("--serve-port", type=int, default=8765)
    parser.add_argument("--proofs-path", default="proofs.jsonl")
    parser.add_argument("--packet-loss", type=float, default=0.0, metavar="RATE",
                        help="Packet loss rate 0.0-1.0 (default: 0.0)")
    parser.add_argument("--jitter-ms", type=float, default=0.0)
    parser.add_argument("--warmup-verify", action=argparse.BooleanOptionalAction, default=None,
                        help="Verify peer mesh visibility before mission (default: True when count > 1)")
    parser.add_argument("--warmup-timeout", type=float, default=10.0,
                        help="Seconds to wait for peer warm-up (default: 10)")
    return parser.parse_args()


def _peer_args(peer_index: int, count: int, base_port: int) -> list[str]:
    current_id = f"drone_{peer_index + 1}"
    peers: list[str] = []
    for idx in range(count):
        if idx == peer_index:
            continue
        peers.extend(["--peer", f"drone_{idx + 1}@127.0.0.1:{base_port + idx}"])
    return ["--peer-id", current_id, "--port", str(base_port + peer_index), *peers]


def _build_command(index: int, count: int, args: argparse.Namespace, output_dir: Path) -> list[str]:
    control_path = output_dir / "control.json"
    command = [
        sys.executable,
        "main.py",
        "--mode",
        "peer",
        "--transport",
        args.transport,
        "--duration",
        str(args.duration),
        "--grid",
        str(args.grid),
        "--tick-seconds",
        str(args.tick_seconds),
        "--tick-delay-seconds",
        str(args.tick_delay_seconds if args.tick_delay_seconds is not None else 0.1),
        "--target",
        args.target,
        "--fail",
        args.fail_drone,
        "--fail-at",
        str(args.fail_at),
        "--proofs",
        args.proofs_path,
        "--control-file",
        str(control_path),
        "--final-map",
        str(output_dir / f"drone_{index + 1}.json"),
    ]
    if args.packet_loss > 0.0:
        command.extend(["--packet-loss", str(args.packet_loss)])
    if args.jitter_ms > 0.0:
        command.extend(["--jitter-ms", str(args.jitter_ms)])
    command.extend(["--control-port", str(args.base_port + index)])
    if args.transport == "foxmq":
        command.extend(
            [
                "--peer-id",
                f"drone_{index + 1}",
                "--mqtt-host",
                args.mqtt_host,
                "--mqtt-port",
                str(args.mqtt_base_port + index),
            ],
        )
        command.extend(_peer_args(index, count, args.base_port))
    else:
        command.extend(_peer_args(index, count, args.base_port))
    return command


def _terminate_processes(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=1.0)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                process.kill()


def _wait_for_processes(processes: list[subprocess.Popen]) -> int:
    exit_code = 0
    try:
        for process in processes:
            exit_code = max(exit_code, process.wait())
    except KeyboardInterrupt:
        exit_code = 130
    finally:
        _terminate_processes(processes)
    return exit_code


def launch_processes(commands: Sequence[list[str]], *, cwd: Path) -> int:
    processes = [subprocess.Popen(command, cwd=cwd) for command in commands]
    return _wait_for_processes(processes)


def _verify_peer_warmup(base_port: int, count: int, timeout: float) -> None:
    if count <= 1:
        return
    deadline = time.monotonic() + timeout
    last_status: dict[int, dict[str, Any]] = {}
    while time.monotonic() < deadline:
        all_ready = True
        missing: list[str] = []
        for idx in range(count):
            port = base_port + idx
            url = f"http://127.0.0.1:{port}/status"
            try:
                with urllib.request.urlopen(url, timeout=0.5) as resp:
                    data = json.loads(resp.read().decode())
                    last_status[idx] = data
                    peers_seen = data.get("peers_seen", [])
                    if len(peers_seen) < count:
                        all_ready = False
                        missing.append(
                            f"{data.get('peer_id', f'drone_{idx + 1}')} sees {len(peers_seen)}/{count} peers"
                        )
            except Exception as exc:
                all_ready = False
                missing.append(f"drone_{idx + 1} unreachable ({exc})")
                last_status.pop(idx, None)
        if all_ready:
            print(f"Warm-up verified: all {count} peers visible")
            return
        time.sleep(0.25)
    print("Warm-up failed: peer visibility not established within timeout", file=sys.stderr)
    for idx in range(count):
        port = base_port + idx
        data = last_status.get(idx)
        if data:
            peer_id = data.get("peer_id", f"drone_{idx + 1}")
            peers_seen = data.get("peers_seen", [])
            expected = [f"drone_{i + 1}" for i in range(count)]
            not_seen = [p for p in expected if p not in peers_seen]
            print(
                f"  {peer_id} sees {len(peers_seen)}/{count} peers, missing: {not_seen}",
                file=sys.stderr,
            )
        else:
            print(f"  drone_{idx + 1} at port {port}: no response", file=sys.stderr)
    raise SystemExit(1)


def _load_live_runtime_module() -> types.ModuleType:
    try:
        return importlib.import_module("scripts.serve_live_runtime")
    except ModuleNotFoundError:
        return importlib.import_module("serve_live_runtime")


def _synthesize_proofs_from_outputs(output_dir: Path, proofs_path: Path) -> None:
    merged: list[dict[str, object]] = []
    seen_keys: set[tuple[object, object, object]] = set()

    if proofs_path.exists():
        for line in proofs_path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = (payload.get("contest_id"), payload.get("type"), payload.get("round_id"))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            payload.setdefault("source", "runtime")
            payload.setdefault("source_mode", "peer")
            payload.setdefault("synthetic", False)
            merged.append(payload)
            if (
                payload.get("type") == "consensus_result"
                and len(payload.get("assignments", [])) > 1
            ):
                auction = {
                    "t": payload.get("t", 0),
                    "type": "auction",
                    "contest_id": payload.get("contest_id"),
                    "message": f"contest resolved for cell {payload.get('cell')}",
                    "source": "derived",
                    "source_mode": str(payload.get("source_mode", "peer")),
                    "derived_from": "consensus_result",
                    "synthetic": True,
                }
                auction_key = (auction.get("contest_id"), auction.get("type"), auction.get("t"))
                if auction_key not in seen_keys:
                    seen_keys.add(auction_key)
                    merged.append(auction)

    for snapshot_path in sorted(output_dir.glob("*.json")):
        try:
            payload = json.loads(snapshot_path.read_text())
        except json.JSONDecodeError:
            continue
        config = payload.get("config", {})
        summary = payload.get("summary", {})
        for event in payload.get("events", []):
            event_type = str(event.get("type", ""))
            if event_type not in FAILOVER_EVENT_TYPES:
                continue
            key = (
                event_type,
                event.get("message"),
                int(event.get("t", 0)),
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            event.setdefault("source", "snapshot")
            event.setdefault("source_mode", str(config.get("source_mode", "peer")))
            event.setdefault("synthetic", False)
            event.setdefault("snapshot_file", snapshot_path.name)
            if isinstance(summary, dict) and summary.get("peer_id") is not None:
                event.setdefault("peer_id", str(summary.get("peer_id")))
            merged.append(event)

    merged.sort(
        key=lambda event: (
            int(str(event.get("t", 0))),
            str(event.get("type", "")),
        ),
    )
    deduped: list[dict[str, object]] = []
    final_seen: set[tuple[object, object, object]] = set()
    for event in merged:
        key = (
            event.get("contest_id"),
            event.get("type"),
            event.get("round_id", event.get("t")),
        )
        if key in final_seen:
            continue
        final_seen.add(key)
        deduped.append(event)
    proofs_path.write_text("".join(json.dumps(event) + "\n" for event in deduped))


def main() -> int:
    args = parse_args()
    if args.warmup_verify is None:
        args.warmup_verify = args.count > 1
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in output_dir.glob("*.json"):
        path.unlink()
    control_path = output_dir / "control.json"
    control_path.write_text(
        json.dumps(
            {
                "tick_seconds": args.tick_seconds,
                "tick_delay_seconds": args.tick_delay_seconds
                if args.tick_delay_seconds is not None
                else 0.1,
                "requested_drone_count": args.count,
            },
            indent=2,
        ),
    )
    proofs_path = Path(args.proofs_path)
    proofs_path.write_text("")
    server: Any | None = None
    server_thread: threading.Thread | None = None
    try:
        serve_module = _load_live_runtime_module()
        server = serve_module.SnapshotHTTPServer(
            (args.serve_host, args.serve_port),
            serve_module.LiveRuntimeRequestHandler,
            snapshot_dir=output_dir,
        )
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
    except OSError:
        server = None
        server_thread = None
    commands = [_build_command(index, args.count, args, output_dir) for index in range(args.count)]
    try:
        if args.warmup_verify and args.count > 1:
            processes = [subprocess.Popen(command, cwd=ROOT) for command in commands]
            try:
                _verify_peer_warmup(args.base_port, args.count, args.warmup_timeout)
            except SystemExit:
                _terminate_processes(processes)
                return 1
            exit_code = _wait_for_processes(processes)
        else:
            exit_code = launch_processes(commands, cwd=ROOT)
    finally:
        if server is not None and server_thread is not None:
            with contextlib.suppress(KeyboardInterrupt):
                server.shutdown()
            with contextlib.suppress(KeyboardInterrupt):
                server.server_close()
            with contextlib.suppress(KeyboardInterrupt):
                server_thread.join(timeout=1.0)
    _synthesize_proofs_from_outputs(output_dir, proofs_path)
    poc_path = ROOT / "proof_of_coordination.json"
    logger = ProofLogger(proofs_path, truncate=False)
    mesh_transport = "foxmq" if args.transport == "foxmq" else "in-process"
    logger.finalize(poc_path, mesh_transport=mesh_transport)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
