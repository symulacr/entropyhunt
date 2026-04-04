from __future__ import annotations

import importlib
import os
from typing import Any

from simulation.peer_protocol import parse_peer_endpoint

Vector3 = tuple[float, float, float]


def controller_api_available() -> bool:
    try:
        importlib.import_module("controller")
    except ModuleNotFoundError:
        return False
    return True


def load_controller_module() -> Any:
    try:
        return importlib.import_module("controller")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Webots Python controller API is not available. Run inside Webots or expose the controller module on PYTHONPATH."
        ) from exc


def create_robot(controller_module: Any | None = None) -> Any:
    module = controller_module or load_controller_module()
    return module.Robot()


def create_supervisor(controller_module: Any | None = None) -> Any:
    module = controller_module or load_controller_module()
    return module.Supervisor()


def basic_time_step(robot: Any) -> int:
    return int(robot.getBasicTimeStep())


def step_robot(robot: Any, time_step: int | None = None) -> int:
    step = basic_time_step(robot) if time_step is None else int(time_step)
    return int(robot.step(step))


def get_node_by_def(supervisor: Any, def_name: str) -> Any | None:
    return supervisor.getFromDef(def_name)


def translation_field(node: Any) -> Any:
    return node.getField("translation")


def node_position(node: Any) -> Vector3:
    if hasattr(node, "getPosition"):
        x, y, z = node.getPosition()
        return (float(x), float(y), float(z))
    x, y, z = translation_field(node).getSFVec3f()
    return (float(x), float(y), float(z))


def set_node_position(node: Any, position: Vector3) -> None:
    translation_field(node).setSFVec3f(list(position))


def runtime_config_from_env() -> Any:
    from simulation.webots_runtime import WebotsRuntimeConfig
    peers = tuple(
        parse_peer_endpoint(value)
        for value in os.environ.get("ENTROPYHUNT_PEERS", "").split(",")
        if value.strip()
    )
    return WebotsRuntimeConfig(
        peer_id=os.environ.get("ENTROPYHUNT_PEER_ID", "drone_1"),
        drone_def=os.environ.get("ENTROPYHUNT_DRONE_DEF", "DRONE_1"),
        host=os.environ.get("ENTROPYHUNT_HOST", "127.0.0.1"),
        port=int(os.environ.get("ENTROPYHUNT_PORT", "0")),
        peers=peers,
        transport=os.environ.get("ENTROPYHUNT_TRANSPORT", "local"),
        mqtt_host=os.environ.get("ENTROPYHUNT_MQTT_HOST", "127.0.0.1"),
        mqtt_port=int(os.environ.get("ENTROPYHUNT_MQTT_PORT", "1883")),
        snapshot_path=os.environ.get("ENTROPYHUNT_SNAPSHOT_PATH", "webots_world/webots_snapshot.json"),
        final_map_path=os.environ.get("ENTROPYHUNT_FINAL_MAP_PATH", "webots_world/webots_final_map.json"),
        max_steps=int(os.environ.get("ENTROPYHUNT_MAX_STEPS", "0")),
    )


def run_webots_supervisor() -> int:
    from simulation.webots_runtime import WebotsPeerRuntime

    runtime = WebotsPeerRuntime(runtime_config_from_env())
    return runtime.run()
