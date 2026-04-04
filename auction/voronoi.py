from __future__ import annotations

from dataclasses import dataclass
from math import dist

from core.certainty_map import Coordinate


@dataclass(frozen=True, slots=True)
class PartitionSeed:
    drone_id: str
    position: Coordinate


@dataclass(frozen=True, slots=True)
class PartitionOwner:
    drone_id: str
    cells: tuple[Coordinate, ...]


def ownership_grid(seeds: list[PartitionSeed], *, size: int) -> list[list[str | None]]:
    if not seeds:
        return [[None for _ in range(size)] for _ in range(size)]

    ranked = sorted(seeds, key=lambda seed: seed.drone_id)
    grid: list[list[str | None]] = []
    for y in range(size):
        row: list[str | None] = []
        for x in range(size):
            owner = min(
                ranked,
                key=lambda seed: (dist(seed.position, (x, y)), seed.drone_id),
            )
            row.append(owner.drone_id)
        grid.append(row)
    return grid


def partition_grid(*, size: int, drone_positions: dict[str, Coordinate]) -> tuple[PartitionOwner, ...]:
    seeds = [PartitionSeed(drone_id=drone_id, position=position) for drone_id, position in drone_positions.items()]
    owners = ownership_grid(seeds, size=size)
    grouped: dict[str, list[Coordinate]] = {drone_id: [] for drone_id in sorted(drone_positions)}
    for y, row in enumerate(owners):
        for x, owner in enumerate(row):
            if owner is not None:
                grouped.setdefault(owner, []).append((x, y))
    return tuple(
        PartitionOwner(drone_id=drone_id, cells=tuple(cells))
        for drone_id, cells in grouped.items()
    )


def _grid_from_partitions(partitions: tuple[PartitionOwner, ...], *, size: int) -> list[list[str | None]]:
    owners: list[list[str | None]] = [[None for _ in range(size)] for _ in range(size)]
    for partition in partitions:
        for x, y in partition.cells:
            owners[y][x] = partition.drone_id
    return owners


def boundary_cells(
    source: list[list[str | None]] | tuple[PartitionOwner, ...],
    *,
    size: int | None = None,
) -> tuple[Coordinate, ...]:
    if not source:
        return tuple()

    if isinstance(source, tuple) and source and isinstance(source[0], PartitionOwner):
        if size is None:
            raise ValueError("size is required when computing boundaries from partitions")
        owners = _grid_from_partitions(source, size=size)
    else:
        owners = source  # type: ignore[assignment]

    height = len(owners)
    width = len(owners[0]) if owners else 0
    boundaries: set[Coordinate] = set()
    for y in range(height):
        for x in range(width):
            owner = owners[y][x]
            neighbors = []
            if x > 0:
                neighbors.append(owners[y][x - 1])
            if x + 1 < width:
                neighbors.append(owners[y][x + 1])
            if y > 0:
                neighbors.append(owners[y - 1][x])
            if y + 1 < height:
                neighbors.append(owners[y + 1][x])
            if any(neighbor != owner for neighbor in neighbors):
                boundaries.add((x, y))
    return tuple(sorted(boundaries))
