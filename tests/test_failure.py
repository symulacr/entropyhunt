from failure.injector import FailureInjector, FailurePlan
from roles.searcher import DroneState


def test_failure_injector_triggers_once_and_marks_drone_unreachable() -> None:
    drones = [DroneState(drone_id="drone_1", position=(0, 0)), DroneState(drone_id="drone_2", position=(1, 0))]
    injector = FailureInjector(FailurePlan(drone_id="drone_2", fail_at_seconds=3))

    assert injector.maybe_trigger(drones, now_seconds=2) is None
    event = injector.maybe_trigger(drones, now_seconds=3)
    assert event is not None
    assert event.drone_id == "drone_2"
    assert drones[1].reachable is False
    assert injector.maybe_trigger(drones, now_seconds=10) is None
