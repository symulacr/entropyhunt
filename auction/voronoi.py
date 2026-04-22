
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.certainty import Coordinate

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

    grid: list[list[str | None]] = [[None for _ in range(size)] for _ in range(size)]
    queue: deque[tuple[int, int, int, int]] = deque()
    claimed_dist: list[list[int]] = [[-1 for _ in range(size)] for _ in range(size)]
    claimed_tie: list[list[int]] = [[-1 for _ in range(size)] for _ in range(size)]

    for idx, seed in enumerate(ranked):
        sx, sy = seed.position
        if (
            0 <= sx < size
            and 0 <= sy < size
            and (
                claimed_dist[sy][sx] == -1 or (0, idx) < (claimed_dist[sy][sx], claimed_tie[sy][sx])
            )
        ):
            grid[sy][sx] = seed.drone_id
            claimed_dist[sy][sx] = 0
            claimed_tie[sy][sx] = idx
            queue.append((0, idx, sx, sy))

    while queue:
        d, tie_idx, x, y = queue.popleft()
        if (d, tie_idx) > (claimed_dist[y][x], claimed_tie[y][x]):
            continue
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < size and 0 <= ny < size:
                nd = d + 1
                new_key = (nd, tie_idx)
                old_key = (claimed_dist[ny][nx], claimed_tie[ny][nx])
                if claimed_dist[ny][nx] == -1 or new_key < old_key:
                    grid[ny][nx] = ranked[tie_idx].drone_id
                    claimed_dist[ny][nx] = nd
                    claimed_tie[ny][nx] = tie_idx
                    queue.append((nd, tie_idx, nx, ny))

    return grid

def partition_grid(
    *,
    size: int,
    drone_positions: dict[str, Coordinate],
) -> tuple[PartitionOwner, ...]:
    seeds = [
        PartitionSeed(drone_id=drone_id, position=position)
        for drone_id, position in drone_positions.items()
    ]
    owners = ownership_grid(seeds, size=size)
    grouped: dict[str, list[Coordinate]] = {drone_id: [] for drone_id in sorted(drone_positions)}
    for y, row in enumerate(owners):
        for x, owner in enumerate(row):
            if owner is not None:
                grouped.setdefault(owner, []).append((x, y))
    return tuple(
        PartitionOwner(drone_id=drone_id, cells=tuple(cells)) for drone_id, cells in grouped.items()
    )

def _grid_from_partitions(
    partitions: tuple[PartitionOwner, ...],
    *,
    size: int,
) -> list[list[str | None]]:
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
        return ()

    if isinstance(source, tuple) and source and isinstance(source[0], PartitionOwner):
        if size is None:
            _msg = "size is required when computing boundaries from partitions"
            raise ValueError(_msg)
        owners: list[list[str | None]] = _grid_from_partitions(source, size=size)
    else:
        owners = source if isinstance(source, list) else []

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
