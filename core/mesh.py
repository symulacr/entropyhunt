from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass
import importlib
import json
import os
import socket
import time
from typing import Any

from core.vertex_bridge import VertexBridge


@dataclass(frozen=True, slots=True)
class MeshEnvelope:
    topic: str
    payload: dict[str, Any]
    timestamp_ms: int
    sender_id: str = "local"
    message_id: str = ""


MeshMessage = MeshEnvelope


@dataclass(frozen=True, slots=True)
class MeshSubscription:
    subscriber_id: str
    topic_pattern: str


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


def _matches_topic(topic_pattern: str, topic: str) -> bool:
    if topic_pattern.endswith("#"):
        return topic.startswith(topic_pattern[:-1])
    return topic == topic_pattern


class InMemoryMeshBus:
    def __init__(self, *, peer_id: str = "local") -> None:
        self.peer_id = peer_id
        self._messages: dict[str, list[MeshEnvelope]] = defaultdict(list)
        self._sequence = 0
        self._subscriptions: dict[str, list[MeshSubscription]] = defaultdict(list)
        self._inboxes: dict[str, deque[MeshEnvelope]] = defaultdict(deque)

    def subscribe(self, subscriber_id: str, topic_pattern: str) -> None:
        subscription = MeshSubscription(subscriber_id=subscriber_id, topic_pattern=topic_pattern)
        if subscription in self._subscriptions[subscriber_id]:
            return
        self._subscriptions[subscriber_id].append(subscription)

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
        resolved_sender = sender_id or self.peer_id
        return MeshEnvelope(
            topic=topic,
            payload=payload,
            timestamp_ms=timestamp_ms,
            sender_id=resolved_sender,
            message_id=message_id or f"{resolved_sender}:{timestamp_ms}:{self._sequence}",
        )

    def _remember(self, envelope: MeshEnvelope) -> MeshEnvelope:
        self._messages[envelope.topic].append(envelope)
        for subscriber_id, subscriptions in self._subscriptions.items():
            if any(_matches_topic(subscription.topic_pattern, envelope.topic) for subscription in subscriptions):
                self._inboxes[subscriber_id].append(envelope)
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

    def poll(
        self,
        subscriber_id: str | None = None,
        *,
        topic_pattern: str | None = None,
    ) -> list[MeshEnvelope]:
        if subscriber_id is None:
            return []
        inbox = self._inboxes[subscriber_id]
        if topic_pattern is None:
            messages = list(inbox)
            inbox.clear()
            return messages
        matched: list[MeshEnvelope] = []
        remaining: deque[MeshEnvelope] = deque()
        while inbox:
            envelope = inbox.popleft()
            if _matches_topic(topic_pattern, envelope.topic):
                matched.append(envelope)
            else:
                remaining.append(envelope)
        self._inboxes[subscriber_id] = remaining
        return matched

    def history(self, topic: str) -> list[MeshEnvelope]:
        return list(self._messages.get(topic, []))

    def latest(self, topic: str) -> MeshEnvelope | None:
        messages = self._messages.get(topic, [])
        return messages[-1] if messages else None

    def count(self) -> int:
        return sum(len(messages) for messages in self._messages.values())

    def close(self) -> None:
        return None


# Swapping the simulation onto NullBus intentionally breaks contested-claim quorum
# collection and result delivery. That breakage is the proof that the mesh became
# load-bearing after fixes 4-5; if votes/results still worked with NullBus, the bus
# would still be decorative.
class NullBus(InMemoryMeshBus):
    def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        timestamp_ms: int,
        sender_id: str | None = None,
        message_id: str | None = None,
    ) -> MeshEnvelope:
        return self._next_envelope(
            topic,
            payload,
            timestamp_ms=timestamp_ms,
            sender_id=sender_id,
            message_id=message_id,
        )

    def history(self, topic: str) -> list[MeshEnvelope]:
        return []

    def latest(self, topic: str) -> MeshEnvelope | None:
        return None

    def count(self) -> int:
        return 0


MeshBus = InMemoryMeshBus


class VertexMeshBus(InMemoryMeshBus):
    """
    Adapter surface for a real Vertex-backed mesh bridge.

    Current status:
    - Vertex handshake / heartbeat was validated separately with the upstream
      warm-up runner (`/tmp/warmup-vertex-rust` in this environment).
    - A Python-facing publish/subscribe bridge for `main.py --mesh real` needs a
      dedicated stdin/stdout helper process. The helper prototype is not yet
      stable against the latest `tashi-vertex` API, so this adapter is present
      but not promoted as the default demo transport.
    """

    def __init__(
        self,
        *,
        peer_id: str = "vertex",
        helper_bin: str | None = None,
    ) -> None:
        super().__init__(peer_id=peer_id)
        self.helper_bin = helper_bin or os.environ.get(
            "ENTROPYHUNT_VERTEX_HELPER",
            "/tmp/warmup-vertex-rust/target/debug/node",
        )
        self.bridge: VertexBridge | None = None
        self._warning: str | None = None
        self.active_mode = "real"
        keypair_path = os.environ.get("ENTROPYHUNT_VERTEX_KEYPAIR", "submission/vertex.key")
        peer_addr = os.environ.get("ENTROPYHUNT_VERTEX_PEER", "127.0.0.1:9000")
        if not os.path.exists(self.helper_bin):
            self._warning = (
                "VertexMeshBus helper binary is missing; publish calls will fall back to the in-process bus only."
            )
            self.active_mode = "stub"
            return
        try:
            self.bridge = VertexBridge(
                binary_path=self.helper_bin,
                keypair_path=keypair_path,
                peer_addr=peer_addr,
            )
            time.sleep(0.05)
            if self.bridge.proc.poll() is not None:
                self.active_mode = "stub"
                self._warning = (
                    "VertexMeshBus bridge helper exited before publish; "
                    f"falling back to in-process delivery. Detail: {self.bridge.last_error()}"
                )
        except Exception as exc:  # pragma: no cover - exercised in runtime attempt
            self._warning = (
                "VertexMeshBus bridge blocked by helper startup mismatch; "
                f"falling back to in-process delivery. Detail: {exc}"
            )
            self.active_mode = "stub"

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
        if self.bridge is None:
            if self._warning is not None:
                print(f"[WARN] {self._warning}")
                self._warning = None
            return envelope
        if not self.bridge.publish(topic, payload):
            self.active_mode = "stub"
            detail = self.bridge.last_error()
            if self._warning is None:
                self._warning = (
                    "VertexMeshBus publish timed out or was rejected; "
                    f"continuing on in-process bus only. detail={detail}"
                )
                print(f"[WARN] {self._warning}")
            self.bridge.close()
            self.bridge = None
        return envelope

    def close(self) -> None:
        if self.bridge is not None:
            self.bridge.close()


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
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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

    def poll(
        self,
        subscriber_id: str | None = None,
        *,
        topic_pattern: str | None = None,
    ) -> list[MeshEnvelope]:
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
        if subscriber_id is None:
            return incoming
        return super().poll(subscriber_id, topic_pattern=topic_pattern)

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

    def poll(
        self,
        subscriber_id: str | None = None,
        *,
        topic_pattern: str | None = None,
    ) -> list[MeshEnvelope]:
        messages = list(self._incoming)
        self._incoming.clear()
        if subscriber_id is None:
            return messages
        return super().poll(subscriber_id, topic_pattern=topic_pattern)

    def close(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
