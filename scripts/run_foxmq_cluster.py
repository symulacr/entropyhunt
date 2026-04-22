from __future__ import annotations

import argparse
import importlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def build_address_book_command_wrapper(
    *,
    foxmq_bin: str,
    host: str,
    port_start: int,
    port_end: int,
    output_dir: Path,
    force: bool,
) -> list[str]:
    try:
        module = importlib.import_module("scripts.setup_foxmq")
    except ModuleNotFoundError:
        module = importlib.import_module("setup_foxmq")
    builder = module.build_address_book_command
    return builder(
        foxmq_bin=foxmq_bin,
        host=host,
        port_start=port_start,
        port_end=port_end,
        output_dir=output_dir,
        force=force,
    )


def build_run_command(
    *,
    foxmq_bin: str,
    config_dir: Path,
    node_index: int,
    mqtt_host: str,
    mqtt_port: int,
    cluster_host: str,
    cluster_port: int,
    allow_anonymous: bool,
) -> list[str]:
    command = [
        foxmq_bin,
        "run",
        "--log=json",
        f"--mqtt-addr={mqtt_host}:{mqtt_port}",
        f"--cluster-addr={cluster_host}:{cluster_port}",
        f"--secret-key-file={config_dir / f'key_{node_index}.pem'}",
    ]
    if allow_anonymous:
        command.append("--allow-anonymous-login")
    command.append(str(config_dir))
    return command


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a local FoxMQ cluster")
    parser.add_argument("--foxmq-bin", default="foxmq")
    parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--mqtt-host", default=os.environ.get("ENTROPYHUNT_MQTT_HOST", "127.0.0.1"))
    parser.add_argument("--mqtt-base-port", type=int, default=1883)
    parser.add_argument("--cluster-host", default=os.environ.get("ENTROPYHUNT_HOST", "127.0.0.1"))
    parser.add_argument("--cluster-base-port", type=int, default=19793)
    parser.add_argument("--config-dir", default="foxmq.d")
    parser.add_argument("--allow-anonymous-login", action="store_true")
    parser.add_argument("--skip-address-book", action="store_true")
    return parser.parse_args()


def _launch_processes(commands: Sequence[list[str]], *, cwd: Path) -> int:
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
    resolved_bin = shutil.which(args.foxmq_bin)
    if resolved_bin is None:
        _msg = f"foxmq binary not found: {args.foxmq_bin!r}"
        raise FileNotFoundError(_msg)
    args.foxmq_bin = resolved_bin
    config_dir = Path(args.config_dir)
    cwd = Path.cwd()
    if not args.skip_address_book:
        subprocess.run(
            build_address_book_command_wrapper(
                foxmq_bin=args.foxmq_bin,
                host=args.cluster_host,
                port_start=args.cluster_base_port,
                port_end=args.cluster_base_port + args.count - 1,
                output_dir=config_dir,
                force=True,
            ),
            check=True,
        )
    commands = [
        build_run_command(
            foxmq_bin=args.foxmq_bin,
            config_dir=config_dir,
            node_index=index,
            mqtt_host=args.mqtt_host,
            mqtt_port=args.mqtt_base_port + index,
            cluster_host=args.cluster_host,
            cluster_port=args.cluster_base_port + index,
            allow_anonymous=args.allow_anonymous_login,
        )
        for index in range(args.count)
    ]
    return _launch_processes(commands, cwd=cwd)


if __name__ == "__main__":
    raise SystemExit(main())
