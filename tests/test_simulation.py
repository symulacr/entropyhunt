import json
from pathlib import Path

from simulation.stub import EntropyHuntSimulation, SimulationConfig


def test_simulation_runs_end_to_end_with_failure_and_survivor(tmp_path: Path) -> None:
    simulation = EntropyHuntSimulation(
        SimulationConfig(
            grid=4,
            drones=5,
            duration=60,
            target=(0, 0),
            fail_drone="drone_2",
            fail_at=5,
            final_map_path=str(tmp_path / "test-final-map.json"),
        )
    )
    summary = simulation.run()
    assert summary["bft_rounds"] >= 1
    assert summary["dropouts"] == 1
    assert summary["survivor_found"] is True
    assert summary["mesh_messages"] > 0


def test_failure_waits_for_heartbeat_timeout_before_stale_release(tmp_path: Path) -> None:
    simulation = EntropyHuntSimulation(
        SimulationConfig(
            grid=4,
            drones=5,
            duration=10,
            target=(3, 3),
            fail_drone="drone_2",
            fail_at=1,
            stop_on_survivor=False,
            final_map_path=str(tmp_path / "test-timeout-final-map.json"),
        )
    )
    simulation.initialise()
    simulation.tick()
    failing = next(drone for drone in simulation.drones if drone.drone_id == "drone_2")
    assert failing.alive is True
    assert failing.reachable is False
    assert failing.status != "stale"

    simulation.tick()
    simulation.tick()
    still_waiting = next(drone for drone in simulation.drones if drone.drone_id == "drone_2")
    assert still_waiting.alive is True

    simulation.tick()
    stale = next(drone for drone in simulation.drones if drone.drone_id == "drone_2")
    assert stale.alive is False
    assert stale.status == "stale"
    assert any("heartbeat timeout" in event["message"] for event in simulation.events)


def test_simulation_continues_full_duration_and_broadcasts_survivor_receipts(tmp_path: Path) -> None:
    simulation = EntropyHuntSimulation(
        SimulationConfig(
            grid=4,
            drones=5,
            duration=30,
            target=(0, 0),
            fail_drone=None,
            stop_on_survivor=False,
            final_map_path=str(tmp_path / "test-full-duration-map.json"),
        )
    )
    summary = simulation.run()
    assert summary["duration_elapsed"] == 30
    assert summary["survivor_found"] is True
    assert summary["survivor_receipts"] >= 1


def test_default_demo_now_reaches_full_completed_coverage(tmp_path: Path) -> None:
    simulation = EntropyHuntSimulation(
        SimulationConfig(
            final_map_path=str(tmp_path / "test-default-final-map.json"),
        )
    )
    summary = simulation.run()
    assert summary["coverage"] == 1.0
    assert summary["coverage_completed"] == 1.0
    assert summary["coverage_current"] <= summary["coverage"]


def test_saved_final_map_includes_bridge_and_partition_metadata(tmp_path: Path) -> None:
    output_path = tmp_path / "final-map.json"
    simulation = EntropyHuntSimulation(
        SimulationConfig(
            grid=4,
            duration=10,
            fail_drone=None,
            final_map_path=str(output_path),
        )
    )
    simulation.run()
    payload = json.loads(output_path.read_text())
    assert "config" in payload
    assert "bridge_snapshot" in payload
    assert "partitions" in payload
    assert "partition_boundaries" in payload
