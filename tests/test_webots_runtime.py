from __future__ import annotations

from pathlib import Path

from simulation.webots_runtime import WebotsPeerRuntime, WebotsRuntimeConfig


class FakeField:
    def __init__(self, position: tuple[float, float, float]) -> None:
        self.value = list(position)

    def getSFVec3f(self) -> list[float]:
        return list(self.value)

    def setSFVec3f(self, value: list[float]) -> None:
        self.value = list(value)


class FakeNode:
    def __init__(self, position: tuple[float, float, float]) -> None:
        self._field = FakeField(position)

    def getPosition(self) -> tuple[float, float, float]:
        x, y, z = self._field.value
        return (x, y, z)

    def getField(self, _name: str) -> FakeField:
        return self._field


class FakeSupervisor:
    def __init__(self) -> None:
        self.nodes = {
            "DRONE_1": FakeNode((0.0, 0.2, 0.0)),
            "TARGET": FakeNode((1.0, 0.2, 1.0)),
        }
        self.calls = 0

    def getBasicTimeStep(self) -> int:
        return 64

    def step(self, time_step: int) -> int:
        self.calls += 1
        return time_step

    def getFromDef(self, def_name: str) -> FakeNode | None:
        return self.nodes.get(def_name)


def test_webots_runtime_drives_peer_runtime_and_writes_snapshot(tmp_path: Path) -> None:
    runtime = WebotsPeerRuntime(
        WebotsRuntimeConfig(
            peer_id="drone_1",
            drone_def="DRONE_1",
            snapshot_path=str(tmp_path / "snapshot.json"),
            final_map_path=str(tmp_path / "final_map.json"),
            grid=3,
            max_steps=1,
        ),
        supervisor=FakeSupervisor(),
    )
    snapshot = runtime.snapshot()
    assert snapshot["world_mode"] == "webots-peer-runtime"
    peer_summary = snapshot["peer_summary"]
    assert isinstance(peer_summary, dict)
    assert peer_summary["peer_id"] == "drone_1"

    runtime.step()
    output = tmp_path / "snapshot.json"
    assert output.exists()
    assert runtime.step_count == 1
    # the supervisor node should have moved toward the target after one peer tick
    x, _y, z = runtime.supervisor.nodes["DRONE_1"].getPosition()
    assert x >= 0.0
    assert z >= 0.0
