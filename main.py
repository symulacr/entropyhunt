from __future__ import annotations

import argparse
import os
import shutil
import signal
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.mesh import (
    FoxMQConfig,
    FoxMQMeshBus,
    LocalPeerConfig,
    LocalPeerMeshBus,
    MeshBusProtocol,
    VertexMeshBus,
)
from simulation.protocol import parse_peer_endpoint
from simulation.runtime import PeerFailureError, PeerRuntime, PeerRuntimeConfig
from simulation.stub import EntropyHuntSimulation, SimulationConfig
from viz.heatmap import SVGRenderOptions, render_html_snapshot, render_svg_heatmap

if TYPE_CHECKING:
    from types import FrameType

    from core.certainty import CertaintyMap


def parse_args() -> argparse.Namespace:
    default_tick_delay = os.environ.get("ENTROPYHUNT_TICK_DELAY_SECONDS")
    parser = argparse.ArgumentParser(description="Run the Entropy Hunt simulation")
    parser.add_argument("--mode", choices=("stub", "peer"), default="stub")
    parser.add_argument("--drones", type=int, default=5)
    parser.add_argument("--grid", type=int, default=10)
    parser.add_argument("--duration", type=int, default=180)
    parser.add_argument("--tick-seconds", type=int, default=1)
    parser.add_argument(
        "--tick-delay-seconds",
        type=float,
        default=float(default_tick_delay) if default_tick_delay else None,
    )
    parser.add_argument("--mesh", choices=("local", "real"), default="local")
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--target", default="7,3")
    parser.add_argument("--fail", dest="fail_drone", default="drone_2")
    parser.add_argument("--fail-at", type=int, default=60)
    parser.add_argument("--stop-on-survivor", action="store_true")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--final-map", default="final_map.json")
    parser.add_argument("--proofs", default="proofs.jsonl")
    parser.add_argument("--control-file", default="")
    parser.add_argument("--svg-map", default=None)
    parser.add_argument("--final-html", default="")
    parser.add_argument("--peer-id", default="drone_1")
    parser.add_argument("--host", default=os.environ.get("ENTROPYHUNT_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--peer", action="append", default=[])
    parser.add_argument("--no-discovery", action="store_true")
    parser.add_argument("--transport", choices=("local", "foxmq"), default="local")
    parser.add_argument("--mqtt-host", default=os.environ.get("ENTROPYHUNT_MQTT_HOST", "127.0.0.1"))
    parser.add_argument("--mqtt-port", type=int, default=1884)
    parser.add_argument("--mqtt-username", default=None)
    parser.add_argument("--mqtt-password", default=None)
    parser.add_argument("--packet-loss", type=float, default=0.0, metavar="RATE",
                        help="Packet loss rate 0.0-1.0 (default: 0.0)")
    parser.add_argument("--jitter-ms", type=float, default=0.0, metavar="MS",
                        help="Latency jitter in milliseconds (default: 0.0)")
    parser.add_argument("--warmup-verify", action=argparse.BooleanOptionalAction, default=None,
                        help="Verify peer mesh visibility before mission (default: True when peers > 1)")
    parser.add_argument("--control-port", type=int, default=0,
                        help="HTTP status port for peer warm-up checks (default: mesh port)")
    return parser.parse_args()


def _render_exports(
    *,
    certainty_map: CertaintyMap,
    drones: list[Any],
    target: tuple[int, int],
    boundary_cells: tuple[tuple[int, int], ...],
    summary: dict[str, object],
    events: list[dict[str, object]],
    svg_map: str | None,
    final_html: str,
) -> None:
    if final_html:
        svg = render_svg_heatmap(
            certainty_map,
            drones,
            SVGRenderOptions(target=target, boundary_cells_override=boundary_cells),
        )
        Path(final_html).write_text(render_html_snapshot(
            title="Entropy Hunt final snapshot",
            summary=summary,
            svg_heatmap=svg,
            events=events,
        ))
    if svg_map:
        svg = render_svg_heatmap(
            certainty_map,
            drones,
            SVGRenderOptions(target=target, boundary_cells_override=boundary_cells),
        )
        Path(svg_map).write_text(svg)


def run_stub_mode(args: argparse.Namespace) -> int:
    target_x, target_y = (int(v) for v in args.target.split(",", maxsplit=1))
    mesh_factory: Callable[[], MeshBusProtocol] | None
    if args.mesh == "real":
        mesh_factory = lambda: VertexMeshBus(strict=True)
        detected_transport = "vertex"
    elif shutil.which("foxmq"):
        mesh_factory = lambda: FoxMQMeshBus(
            peer_id="simulation",
            config=FoxMQConfig(mqtt_host="127.0.0.1", mqtt_port=1884, lazy_connect=True),
        )
        detected_transport = "foxmq"
    else:
        try:
            _udp = LocalPeerMeshBus(peer_id="simulation", config=LocalPeerConfig())
            _udp.close()
            mesh_factory = lambda: LocalPeerMeshBus(
                peer_id="simulation", config=LocalPeerConfig(),
            )
            detected_transport = "udp"
        except OSError:
            mesh_factory = None
            detected_transport = "in-process"
    config = SimulationConfig(
        drones=args.drones,
        grid=args.grid,
        duration=args.duration,
        tick_seconds=args.tick_seconds,
        target=(target_x, target_y),
        fail_drone=args.fail_drone,
        fail_at=args.fail_at,
        stop_on_survivor=args.stop_on_survivor,
        seed=args.seed,
        final_map_path=args.final_map,
        proofs_path=args.proofs,
        packet_loss=args.packet_loss,
        jitter_ms=args.jitter_ms,
        transport=detected_transport,
    )
    simulation = EntropyHuntSimulation(config, mesh_factory=mesh_factory)
    tick_delay_seconds = max(
        0.0,
        float(args.tick_delay_seconds)
        if args.tick_delay_seconds is not None
        else 0.02,
    )
    record_dir = Path("demo_frames")
    if args.record:
        shutil.rmtree(record_dir, ignore_errors=True)
        record_dir.mkdir(parents=True, exist_ok=True)

    def render_state(state: dict[str, Any]) -> None:
        if args.record:
            (record_dir / f"frame_{int(state.get('elapsed', 0)):04d}.txt").write_text(
                str(state)
            )

    simulation.initialise()
    render_state(simulation.get_state())
    time.sleep(tick_delay_seconds)
    try:
        for _ in range(config.duration // config.tick_seconds):
            if _shutdown_requested:
                break
            simulation.tick()
            render_state(simulation.get_state())
            time.sleep(tick_delay_seconds)
            if simulation.survivor_found and config.stop_on_survivor:
                break

        if simulation.survivor_found:
            final_state = simulation.get_state()
            for index in range(100):
                if _shutdown_requested:
                    break
                final_state["flash_target"] = index % 2 == 0
                render_state(final_state)
                time.sleep(0.05)
            final_state["flash_target"] = False

        summary = simulation.finalize()
        _render_exports(
            certainty_map=simulation.certainty_map,
            drones=list(simulation.drones),
            target=config.target,
            boundary_cells=simulation.partition_boundary_cells(),
            summary=summary,
            events=simulation.events,
            svg_map=args.svg_map,
            final_html=args.final_html,
        )
    finally:
        simulation.mesh.close()
    return 0


def run_peer_mode(args: argparse.Namespace) -> int:
    target_x, target_y = (int(v) for v in args.target.split(",", maxsplit=1))
    config = PeerRuntimeConfig(
        peer_id=args.peer_id,
        host=args.host,
        port=args.port,
        peers=tuple(parse_peer_endpoint(v) for v in args.peer),
        transport=args.transport,
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
        mqtt_username=args.mqtt_username,
        mqtt_password=args.mqtt_password,
        grid=args.grid,
        duration=args.duration,
        tick_seconds=args.tick_seconds,
        tick_delay_seconds=args.tick_delay_seconds,
        target=(target_x, target_y),
        stop_on_survivor=args.stop_on_survivor,
        fail_at=args.fail_at if args.fail_drone == args.peer_id else None,
        final_map_path=args.final_map,
        proofs_path=args.proofs,
        control_file=args.control_file,
        control_port=args.control_port,
        packet_loss=args.packet_loss,
        jitter_ms=args.jitter_ms,
        discovery_enabled=not args.no_discovery,
    )
    runtime = PeerRuntime(config)
    exit_code = 0
    try:
        summary = runtime.run()
    except PeerFailureError as exc:
        summary = runtime.summary()
        exit_code = exc.exit_code
    _render_exports(
        certainty_map=runtime.certainty_map,
        drones=list(runtime.peer_drones.values()),
        target=config.target,
        boundary_cells=(),
        summary=summary,
        events=runtime.events,
        svg_map=args.svg_map,
        final_html=args.final_html,
    )
    return exit_code


_shutdown_requested = False


def _signal_handler(signum: int, _frame: FrameType | None) -> None:
    global _shutdown_requested
    _shutdown_requested = True
    sys.stderr.write(f"Received {signal.Signals(signum).name}, initiating graceful shutdown...\n")
    raise KeyboardInterrupt


def _require_mesh_secret() -> None:
    if not os.environ.get("ENTROPYHUNT_MESH_SECRET", "").strip():
        sys.stderr.write(
            "Error: ENTROPYHUNT_MESH_SECRET environment variable must be set and non-empty "
            "when using --mesh real or --transport foxmq.\n"
            "Copy .env.example to .env, fill in your secret, then source it:\n"
            "  cp .env.example .env  # edit .env\n"
            "  export $(cat .env | xargs)\n",
        )
        raise SystemExit(1)


def main() -> int:
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    args = parse_args()
    if args.warmup_verify is None:
        args.warmup_verify = args.mode != "stub" and len(args.peer) > 0
    if args.mesh == "real" or args.transport == "foxmq":
        _require_mesh_secret()
    if args.grid < 1:
        raise SystemExit("Error: --grid must be >= 1")
    if args.drones < 1:
        raise SystemExit("Error: --drones must be >= 1")
    if args.duration < 0:
        raise SystemExit("Error: --duration must be >= 0")
    if args.tick_seconds < 1:
        raise SystemExit("Error: --tick-seconds must be >= 1")
    if args.mode != "peer" and args.control_file:
        raise SystemExit("--control-file is only supported in peer mode")
    if args.mode == "peer":
        return run_peer_mode(args)
    return run_stub_mode(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
