import json
from pathlib import Path

from core.mesh import NullBus
from simulation.stub import EntropyHuntSimulation, SimulationConfig


def test_simulation_runs_end_to_end_with_failure_and_survivor(tmp_path: Path) -> None:
    simulation = EntropyHuntSimulation(
        SimulationConfig(
            grid=4,
            drones=5,
            duration=150,
            target=(0, 0),
            fail_drone="drone_2",
            fail_at=5,
            final_map_path=str(tmp_path / "test-final-map.json"),
            proofs_path=str(tmp_path / "proofs.jsonl"),
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
            proofs_path=str(tmp_path / "timeout-proofs.jsonl"),
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
            duration=140,
            target=(0, 0),
            fail_drone=None,
            stop_on_survivor=False,
            final_map_path=str(tmp_path / "test-full-duration-map.json"),
            proofs_path=str(tmp_path / "full-duration-proofs.jsonl"),
        )
    )
    summary = simulation.run()
    assert summary["duration_elapsed"] == 140
    assert summary["survivor_found"] is True
    assert summary["survivor_receipts"] >= 1


def test_default_demo_emits_proofs_in_required_order(tmp_path: Path) -> None:
    proofs_path = tmp_path / "proofs.jsonl"
    simulation = EntropyHuntSimulation(
        SimulationConfig(
            final_map_path=str(tmp_path / "test-default-final-map.json"),
            proofs_path=str(proofs_path),
        )
    )
    simulation.run()
    events = [json.loads(line) for line in proofs_path.read_text().splitlines()]
    first_auction = next(event for event in events if event["type"] == "auction")
    failure = next(event for event in events if event["type"] == "failure")
    reclaim = next(event for event in events if event["type"] == "zone_priority_reclaim")
    survivor = next(event for event in events if event["type"] == "survivor_found")

    assert first_auction["t"] < 30
    assert failure["t"] == 60
    assert reclaim["t"] - failure["t"] <= 5
    assert survivor["t"] > 90
    assert len(events) >= 20
    assert all(event["source"] == "runtime" for event in events)
    assert all(event["source_mode"] == "stub" for event in events)
    assert all(event["synthetic"] is False for event in events)


def test_saved_final_map_includes_bridge_and_partition_metadata(tmp_path: Path) -> None:
    output_path = tmp_path / "final-map.json"
    simulation = EntropyHuntSimulation(
        SimulationConfig(
            grid=4,
            duration=10,
            fail_drone=None,
            final_map_path=str(output_path),
            proofs_path=str(tmp_path / "final-map-proofs.jsonl"),
        )
    )
    simulation.run()
    payload = json.loads(output_path.read_text())
    assert "config" in payload
    assert "stats" in payload
    assert "bridge_snapshot" in payload
    assert "partitions" in payload
    assert "partition_boundaries" in payload
    assert payload["config"]["source_mode"] == "stub"
    assert payload["config"]["snapshot_provenance"] == "stub-runtime-export"
    assert payload["config"]["synthetic"] is False


def test_null_bus_breaks_contested_claim_quorum(tmp_path: Path) -> None:
    simulation = EntropyHuntSimulation(
        SimulationConfig(
            duration=5,
            final_map_path=str(tmp_path / "null-bus-map.json"),
            proofs_path=str(tmp_path / "null-bus-proofs.jsonl"),
        ),
        mesh_factory=NullBus,
    )
    try:
        simulation.initialise()
    except RuntimeError as exc:
        assert "failed quorum collection" in str(exc)
    else:
        raise AssertionError("NullBus should break contested-claim quorum collection")
