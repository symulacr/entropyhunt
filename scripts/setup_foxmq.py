from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path


def build_address_book_command(
    *,
    foxmq_bin: str,
    host: str,
    port_start: int,
    port_end: int,
    output_dir: Path,
    force: bool,
) -> list[str]:
    command = [
        foxmq_bin,
        "address-book",
        "from-range",
        "-O",
        str(output_dir),
    ]
    if force:
        command.append("--force")
    command.extend([host, str(port_start), str(port_end)])
    return command


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a FoxMQ address book for local clusters")
    parser.add_argument("--foxmq-bin", default="foxmq")
    parser.add_argument("--host", default=os.environ.get("ENTROPYHUNT_HOST", "127.0.0.1"))
    parser.add_argument("--port-start", type=int, default=19793)
    parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--output-dir", default="foxmq.d")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    resolved_bin = shutil.which(args.foxmq_bin)
    if resolved_bin is None:
        _msg = f"foxmq binary not found: {args.foxmq_bin!r}"
        raise FileNotFoundError(_msg)
    args.foxmq_bin = resolved_bin
    output_dir = Path(args.output_dir)
    command = build_address_book_command(
        foxmq_bin=args.foxmq_bin,
        host=args.host,
        port_start=args.port_start,
        port_end=args.port_start + args.count - 1,
        output_dir=output_dir,
        force=args.force,
    )
    subprocess.run(command, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
