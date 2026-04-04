from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass
import importlib
import json
import socket
from typing import Any


@dataclass(frozen=True, slots=True)
class MeshEnvelope:
    topic: str
    payload: dict[str, Any]
    timestamp_ms: int
    sender_id: str = "local"
    message_id: str = ""


MeshMessage = MeshEnvelope


def encode_envelope(envelope: MeshEnvelope) -> bytes:
    return (json.dumps(asdict(envelope), separators=(",", ":")) + "\n").encode("utf-8")


def decode_envelope(packet: bytes) -> MeshEnvelope:
    payload = json.loads(packet.decode("utf-8"))
    return MeshEnvelope(
        topic=str(payload["topic"]),
        payload=dict(payload["payload"]),
        timestamp_ms=int(payload["timestamp_ms"]),
        sender_id=str(payload["sender_id"]),
        message_id=str(payload["message_id"]),
    )


class InMemoryMeshBus:
    def __init__(self, *, peer_id: str = "local") -> None:
        self.peer_id = peer_id
        self._messages: dict[str, list[MeshEnvelope]] = defaultdict(list)
        self._sequence = 0

    def _next_envelope(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        timestamp_ms: int,
        sender_id: str | None = None,
        message_id: str | None = None,
    ) -> MeshEnvelope:
        self._sequence += 1
        return MeshEnvelope(
            topic=topic,
            payload=payload,
            timestamp_ms=timestamp_ms,
            sender_id=sender_id or self.peer_id,
            message_id=message_id or f"{sender_id or self.peer_id}:{timestamp_ms}:{self._sequence}",
        )

    def _remember(self, envelope: MeshEnvelope) -> MeshEnvelope:
        self._messages[envelope.topic].append(envelope)
        return envelope

    def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        timestamp_ms: int,
        sender_id: str | None = None,
        message_id: str | None = None,
    ) -> MeshEnvelope:
        return self._remember(
            self._next_envelope(
                topic,
                payload,
                timestamp_ms=timestamp_ms,
                sender_id=sender_id,
                message_id=message_id,
            )
        )

    def poll(self) -> list[MeshEnvelope]:
        return []

    def history(self, topic: str) -> list[MeshEnvelope]:
        return list(self._messages.get(topic, []))

    def latest(self, topic: str) -> MeshEnvelope | None:
        messages = self._messages.get(topic, [])
        return messages[-1] if messages else None

    def count(self) -> int:
        return sum(len(messages) for messages in self._messages.values())

    def close(self) -> None:
        return None


MeshBus = InMemoryMeshBus


class LocalPeerMeshBus(InMemoryMeshBus):
    def __init__(
        self,
        *,
        peer_id: str,
        bind_host: str = "127.0.0.1",
        bind_port: int = 0,
        peer_addresses: list[tuple[str, int]] | None = None,
    ) -> None:
        super().__init__(peer_id=peer_id)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind((bind_host, bind_port))
        self._socket.setblocking(False)
        self._bind_host, self._bind_port = self._socket.getsockname()
        self._peer_addresses = list(peer_addresses or [])
        self._seen_message_ids: set[str] = set()

    @property
    def bind_address(self) -> tuple[str, int]:
        return (self._bind_host, self._bind_port)

    def set_peers(self, peer_addresses: list[tuple[str, int]]) -> None:
        self._peer_addresses = list(peer_addresses)

    def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        timestamp_ms: int,
        sender_id: str | None = None,
        message_id: str | None = None,
    ) -> MeshEnvelope:
        envelope = super().publish(
            topic,
            payload,
            timestamp_ms=timestamp_ms,
            sender_id=sender_id,
            message_id=message_id,
        )
        self._seen_message_ids.add(envelope.message_id)
        encoded = encode_envelope(envelope)
        for host, port in self._peer_addresses:
            self._socket.sendto(encoded, (host, port))
        return envelope

    def poll(self) -> list[MeshEnvelope]:
        incoming: list[MeshEnvelope] = []
        while True:
            try:
                packet, _ = self._socket.recvfrom(65_535)
            except BlockingIOError:
                break
            envelope = decode_envelope(packet)
            if envelope.message_id in self._seen_message_ids:
                continue
            self._seen_message_ids.add(envelope.message_id)
            self._remember(envelope)
            incoming.append(envelope)
        return incoming

    def close(self) -> None:
        self._socket.close()


class FoxMQMeshBus(InMemoryMeshBus):
    def __init__(
        self,
        *,
        peer_id: str,
        mqtt_host: str = "127.0.0.1",
        mqtt_port: int = 1883,
        username: str | None = None,
        password: str | None = None,
        client_id: str | None = None,
    ) -> None:
        super().__init__(peer_id=peer_id)
        self._incoming: deque[MeshEnvelope] = deque()
        self._seen_message_ids: set[str] = set()
        try:
            mqtt_module = importlib.import_module("paho.mqtt.client")
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "FoxMQMeshBus requires the optional 'paho-mqtt' package. "
                "Install it before using --transport foxmq."
            ) from exc
        self._mqtt = mqtt_module
        self._client = mqtt_module.Client(client_id=client_id or peer_id)
        if username is not None or password is not None:
            self._client.username_pw_set(username=username, password=password)
        self._client.on_message = self._on_message
        self._client.connect(mqtt_host, mqtt_port)
        self._client.subscribe("swarm/#")
        self._client.loop_start()

    def _on_message(self, _client: Any, _userdata: Any, message: Any) -> None:
        envelope = decode_envelope(message.payload)
        if envelope.message_id in self._seen_message_ids:
            return
        self._seen_message_ids.add(envelope.message_id)
        self._remember(envelope)
        self._incoming.append(envelope)

    def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        timestamp_ms: int,
        sender_id: str | None = None,
        message_id: str | None = None,
    ) -> MeshEnvelope:
        envelope = super().publish(
            topic,
            payload,
            timestamp_ms=timestamp_ms,
            sender_id=sender_id,
            message_id=message_id,
        )
        self._seen_message_ids.add(envelope.message_id)
        self._client.publish(topic, encode_envelope(envelope), qos=1)
        return envelope

    def poll(self) -> list[MeshEnvelope]:
        messages = list(self._incoming)
        self._incoming.clear()
        return messages

    def close(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
