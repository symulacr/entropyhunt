from __future__ import annotations

import importlib

import pytest

from simulation import webots_controller


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
        self.nodes = {"DRONE_1": FakeNode((1.0, 0.2, 3.0))}

    def getBasicTimeStep(self) -> int:
        return 64

    def step(self, time_step: int) -> int:
        return time_step

    def getFromDef(self, def_name: str) -> FakeNode | None:
        return self.nodes.get(def_name)


class FakeControllerModule:
    class Robot(FakeSupervisor):
        pass

    class Supervisor(FakeSupervisor):
        pass


def test_load_controller_module_raises_clear_error_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _missing(name: str) -> object:
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(importlib, "import_module", _missing)
    with pytest.raises(RuntimeError):
        webots_controller.load_controller_module()


def test_controller_helpers_work_with_injected_fake_module() -> None:
    supervisor = webots_controller.create_supervisor(FakeControllerModule)
    assert webots_controller.basic_time_step(supervisor) == 64
    assert webots_controller.step_robot(supervisor) == 64
    node = webots_controller.get_node_by_def(supervisor, "DRONE_1")
    assert node is not None
    assert webots_controller.node_position(node) == (1.0, 0.2, 3.0)
    webots_controller.set_node_position(node, (2.0, 0.2, -1.0))
    assert webots_controller.node_position(node) == (2.0, 0.2, -1.0)


def test_runtime_config_from_env_parses_peer_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTROPYHUNT_PEER_ID", "drone_3")
    monkeypatch.setenv("ENTROPYHUNT_DRONE_DEF", "DRONE_3")
    monkeypatch.setenv("ENTROPYHUNT_TRANSPORT", "foxmq")
    monkeypatch.setenv("ENTROPYHUNT_MQTT_PORT", "1999")
    monkeypatch.setenv("ENTROPYHUNT_PEERS", "drone_1@127.0.0.1:9101,drone_2@127.0.0.1:9102")
    config = webots_controller.runtime_config_from_env()
    assert config.peer_id == "drone_3"
    assert config.drone_def == "DRONE_3"
    assert config.transport == "foxmq"
    assert config.mqtt_port == 1999
    assert len(config.peers) == 2
