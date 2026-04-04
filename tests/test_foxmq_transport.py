from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.mesh import FoxMQMeshBus, MeshEnvelope, encode_envelope
from scripts.run_foxmq_cluster import build_run_command
from scripts.setup_foxmq import build_address_book_command


class FakePublishedClient:
    def __init__(self, client_id: str | None = None) -> None:
        self.client_id = client_id
        self.on_message = None
        self.published: list[tuple[str, bytes, int]] = []
        self.subscriptions: list[str] = []
        self.connected_to: tuple[str, int] | None = None

    def username_pw_set(self, username: str | None = None, password: str | None = None) -> None:
        self.username = username
        self.password = password

    def connect(self, host: str, port: int) -> None:
        self.connected_to = (host, port)

    def subscribe(self, topic: str) -> None:
        self.subscriptions.append(topic)

    def loop_start(self) -> None:
        return None

    def loop_stop(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def publish(self, topic: str, payload: bytes, qos: int = 0) -> None:
        self.published.append((topic, payload, qos))


class FakeMqttModule:
    def __init__(self) -> None:
        self.last_client: FakePublishedClient | None = None

    def Client(self, client_id: str | None = None) -> FakePublishedClient:
        self.last_client = FakePublishedClient(client_id)
        return self.last_client


def test_foxmq_mesh_bus_publishes_and_receives_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = FakeMqttModule()

    def _import_module(name: str) -> object:
        if name == "paho.mqtt.client":
            return fake_module
        return importlib.import_module(name)

    monkeypatch.setattr(importlib, "import_module", _import_module)
    bus = FoxMQMeshBus(peer_id="drone_1", mqtt_host="127.0.0.1", mqtt_port=1884)
    try:
        bus.publish("swarm/test", {"value": 5}, timestamp_ms=100)
        assert fake_module.last_client is not None
        assert fake_module.last_client.connected_to == ("127.0.0.1", 1884)
        assert fake_module.last_client.subscriptions == ["swarm/#"]
        assert fake_module.last_client.published[0][0] == "swarm/test"

        incoming = MeshEnvelope(
            topic="swarm/test",
            payload={"value": 9},
            timestamp_ms=101,
            sender_id="drone_2",
            message_id="drone_2:101:1",
        )
        assert fake_module.last_client.on_message is not None
        fake_module.last_client.on_message(None, None, SimpleNamespace(payload=encode_envelope(incoming)))
        polled = bus.poll()
        assert polled == [incoming]
        assert bus.latest("swarm/test") == incoming
    finally:
        bus.close()


def test_foxmq_script_command_builders_match_official_port_mapping() -> None:
    address_book = build_address_book_command(
        foxmq_bin="foxmq",
        host="127.0.0.1",
        port_start=19793,
        port_end=19796,
        output_dir=Path("foxmq.d"),
        force=True,
    )
    assert address_book == [
        "foxmq",
        "address-book",
        "from-range",
        "-O",
        "foxmq.d",
        "--force",
        "127.0.0.1",
        "19793",
        "19796",
    ]

    run_command = build_run_command(
        foxmq_bin="foxmq",
        config_dir=Path("foxmq.d"),
        node_index=1,
        mqtt_host="127.0.0.1",
        mqtt_port=1884,
        cluster_host="127.0.0.1",
        cluster_port=19794,
        allow_anonymous=True,
    )
    assert "--mqtt-addr=127.0.0.1:1884" in run_command
    assert "--cluster-addr=127.0.0.1:19794" in run_command
    assert "--allow-anonymous-login" in run_command
    assert f"--secret-key-file={Path("foxmq.d") / "key_1.pem"}" in run_command
