
from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from auction.voronoi import PartitionOwner, partition_grid
from auction.voronoi import boundary_cells as voronoi_boundary_cells
from simulation.webots_bridge import build_bridge_snapshot

if TYPE_CHECKING:
    from pathlib import Path

    from core.certainty import CertaintyMap, Coordinate
    from roles.drone import DroneState

class SnapshotExporter:

    def __init__(self, config: Any, certainty_map: CertaintyMap, drones: list[DroneState]) -> None:
        self.config = config
        self.certainty_map = certainty_map
        self.drones = drones

    def claimed_owner_map(self) -> dict[Coordinate, str]:
        return {
            drone.claimed_cell: drone.drone_id
            for drone in self.drones
            if drone.alive and drone.reachable and drone.claimed_cell is not None
        }

    def partition_snapshot(self) -> tuple[PartitionOwner, ...]:
        return partition_grid(
            size=self.config.grid,
            drone_positions={
                drone.drone_id: drone.position
                for drone in self.drones
                if drone.alive and drone.reachable
            },
        )

    def partition_boundary_cells(self) -> tuple[Coordinate, ...]:
        return voronoi_boundary_cells(self.partition_snapshot(), size=self.config.grid)

    def save_final_map(
        self,
        path: Path,
        summary: dict[str, Any],
        events: list[dict[str, Any]],
    ) -> None:
        partitions = self.partition_snapshot()
        claimed_owner_map = self.claimed_owner_map()
        config = {
            **asdict(self.config),
            "source_mode": "stub",
            "snapshot_provenance": "stub-runtime-export",
            "synthetic": False,
            "requested_drone_count": self.config.drones,
            "control_capabilities": {
                "tick_seconds": "unavailable",
                "tick_delay_seconds": "unavailable",
                "requested_drone_count": "unavailable",
            },
        }
        payload = {
            "summary": summary,
            "stats": {
                "coverage": summary["coverage_current"],
                "average_entropy": summary["average_entropy"],
                "auctions": summary["auctions"],
                "dropouts": summary["dropouts"],
                "consensus_rounds": summary["consensus_rounds"],
                "elapsed": summary["duration_elapsed"],
            },
            "config": config,
            "events": events,
            "grid": self.certainty_map.to_rows(claimed_owner_map),
            "partitions": [
                {"drone_id": partition.drone_id, "cells": list(partition.cells)}
                for partition in partitions
            ],
            "partition_boundaries": list(self.partition_boundary_cells()),
            "bridge_snapshot": build_bridge_snapshot(
                self.drones,
                tick_seconds=self.config.tick_seconds,
            ),
        }
        path.write_text(json.dumps(payload, indent=2) + "\n")
