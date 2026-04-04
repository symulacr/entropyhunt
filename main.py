from __future__ import annotations

import argparse
import json

from simulation.stub import EntropyHuntSimulation, SimulationConfig
from viz.heatmap import render_ascii_heatmap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Entropy Hunt stub simulation")
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
