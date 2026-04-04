from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from simulation.peer_protocol import parse_peer_endpoint
from simulation.peer_runtime import PeerRuntime, PeerRuntimeConfig
from simulation.stub import EntropyHuntSimulation, SimulationConfig
from viz.heatmap import render_ascii_heatmap, render_html_snapshot, render_svg_heatmap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Entropy Hunt simulation")
    parser.add_argument("--mode", choices=("stub", "peer"), default="stub")
    parser.add_argument("--drones", type=int, default=5)
    parser.add_argument("--grid", type=int, default=10)
    parser.add_argument("--duration", type=int, default=180)
    parser.add_argument("--tick-seconds", type=int, default=1)
    parser.add_argument("--target", default="7,3")
    parser.add_argument("--fail", dest="fail_drone", default="drone_2")
    parser.add_argument("--fail-at", type=int, default=60)
    parser.add_argument("--stop-on-survivor", action="store_true")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--final-map", default="final_map.json")
    parser.add_argument("--svg-map", default=None)
    parser.add_argument("--final-html", default="")
    parser.add_argument("--peer-id", default="drone_1")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--peer", action="append", default=[])
    parser.add_argument("--transport", choices=("local", "foxmq"), default="local")
    parser.add_argument("--mqtt-host", default="127.0.0.1")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--mqtt-username", default=None)
    parser.add_argument("--mqtt-password", default=None)
    return parser.parse_args()


def _render_exports(
    certainty_map: Any,
    drones: Sequence[Any],
    *,
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
            list(drones),
            target=target,
            boundary_cells_override=boundary_cells,
        )
        html = render_html_snapshot(
            title="Entropy Hunt final snapshot",
            summary=summary,
            svg_heatmap=svg,
            events=events,
        )
        Path(final_html).write_text(html)
    if svg_map:
        svg = render_svg_heatmap(
            certainty_map,
            list(drones),
            target=target,
            boundary_cells_override=boundary_cells,
        )
        Path(svg_map).write_text(svg)


def run_stub_mode(args: argparse.Namespace) -> int:
    target_x, target_y = (int(value) for value in args.target.split(",", maxsplit=1))
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
    )
    simulation = EntropyHuntSimulation(config)
    summary = simulation.run()
    print(render_ascii_heatmap(simulation.certainty_map, simulation.drones))
    print(json.dumps(summary, indent=2))
    _render_exports(
        simulation.certainty_map,
        simulation.drones,
        target=config.target,
        boundary_cells=simulation.partition_boundary_cells(),
        summary=summary,
        events=simulation.events,
        svg_map=args.svg_map,
        final_html=args.final_html,
    )
    return 0


def run_peer_mode(args: argparse.Namespace) -> int:
    target_x, target_y = (int(value) for value in args.target.split(",", maxsplit=1))
    config = PeerRuntimeConfig(
        peer_id=args.peer_id,
        host=args.host,
        port=args.port,
        peers=tuple(parse_peer_endpoint(value) for value in args.peer),
        transport=args.transport,
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
        mqtt_username=args.mqtt_username,
        mqtt_password=args.mqtt_password,
        grid=args.grid,
        duration=args.duration,
        tick_seconds=args.tick_seconds,
        target=(target_x, target_y),
        stop_on_survivor=args.stop_on_survivor,
        fail_at=args.fail_at if args.fail_drone == args.peer_id else None,
        final_map_path=args.final_map,
    )
    runtime = PeerRuntime(config)
    summary = runtime.run()
    print(render_ascii_heatmap(runtime.certainty_map, list(runtime.peer_drones.values())))
    print(json.dumps(summary, indent=2))
    _render_exports(
        runtime.certainty_map,
        list(runtime.peer_drones.values()),
        target=config.target,
        boundary_cells=tuple(),
        summary=summary,
        events=runtime.events,
        svg_map=args.svg_map,
        final_html=args.final_html,
    )
    return 0


def main() -> int:
    args = parse_args()
    if args.mode == "peer":
        return run_peer_mode(args)
    return run_stub_mode(args)


if __name__ == "__main__":
    raise SystemExit(main())
