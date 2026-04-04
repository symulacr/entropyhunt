from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Sequence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a local multi-peer Entropy Hunt demo")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--base-port", type=int, default=9101)
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--grid", type=int, default=10)
    parser.add_argument("--tick-seconds", type=int, default=1)
    parser.add_argument("--output-dir", default="peer-runs")
    parser.add_argument("--transport", choices=("local", "foxmq"), default="local")
    parser.add_argument("--mqtt-host", default="127.0.0.1")
    parser.add_argument("--mqtt-base-port", type=int, default=1883)
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
        "--final-map",
        str(output_dir / f"drone_{index + 1}.json"),
    ]
    if args.transport == "foxmq":
        command.extend([
            "--peer-id",
            f"drone_{index + 1}",
            "--mqtt-host",
            args.mqtt_host,
            "--mqtt-port",
            str(args.mqtt_base_port + index),
        ])
    else:
        command.extend(_peer_args(index, count, args.base_port))
    return command


def launch_processes(commands: Sequence[list[str]], *, cwd: Path) -> int:
    processes = [subprocess.Popen(command, cwd=cwd) for command in commands]
    exit_code = 0
    try:
        for process in processes:
            exit_code = max(exit_code, process.wait())
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
    return exit_code


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    commands = [_build_command(index, args.count, args, output_dir) for index in range(args.count)]
    return launch_processes(commands, cwd=Path(__file__).resolve().parent.parent)


if __name__ == "__main__":
    raise SystemExit(main())
