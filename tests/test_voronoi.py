from auction.voronoi import PartitionOwner, PartitionSeed, boundary_cells, ownership_grid, partition_grid


def test_ownership_grid_breaks_distance_ties_by_drone_id() -> None:
    owners = ownership_grid(
        [PartitionSeed("drone_2", (0, 1)), PartitionSeed("drone_1", (2, 1))],
        size=3,
    )
    assert owners[1][1] == "drone_1"


def test_partition_grid_and_boundary_cells_cover_grid() -> None:
    partitions = partition_grid(
        size=3,
        drone_positions={"drone_1": (0, 0), "drone_2": (2, 2)},
    )
    assert isinstance(partitions[0], PartitionOwner)
    assert sum(len(partition.cells) for partition in partitions) == 9
    boundaries = boundary_cells(partitions, size=3)
    assert boundaries
