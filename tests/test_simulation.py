from simulation.stub import EntropyHuntSimulation, SimulationConfig


def test_simulation_runs_end_to_end_with_failure_and_survivor() -> None:
    simulation = EntropyHuntSimulation(
        SimulationConfig(
            grid=4,
            drones=5,
            duration=60,
            target=(0, 0),
            fail_drone="drone_2",
            fail_at=5,
            final_map_path="test-final-map.json",
        )
    )
    summary = simulation.run()
    assert summary["bft_rounds"] >= 1
    assert summary["dropouts"] == 1
    assert summary["survivor_found"] is True
    assert summary["mesh_messages"] > 0


def test_failure_waits_for_heartbeat_timeout_before_stale_release() -> None:
    simulation = EntropyHuntSimulation(
        SimulationConfig(
            grid=4,
            drones=5,
            duration=10,
            target=(3, 3),
            fail_drone="drone_2",
            fail_at=1,
            stop_on_survivor=False,
            final_map_path="test-timeout-final-map.json",
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


def test_simulation_continues_full_duration_and_broadcasts_survivor_receipts() -> None:
    simulation = EntropyHuntSimulation(
        SimulationConfig(
            grid=4,
            drones=5,
            duration=30,
            target=(0, 0),
            fail_drone=None,
            stop_on_survivor=False,
            final_map_path="test-full-duration-map.json",
        )
    )
    summary = simulation.run()
    assert summary["duration_elapsed"] == 30
    assert summary["survivor_found"] is True
    assert summary["survivor_receipts"] >= 1
