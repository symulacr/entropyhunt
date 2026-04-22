from __future__ import annotations

import contextlib
import hashlib as _hashlib
import hmac as _hmac
import importlib
import json
import logging
import os
import secrets
import socket
import subprocess
import tempfile
import threading
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from typing import cast as _cast

if TYPE_CHECKING:
    from core.mqtt_stubs import (
        MqttClient,
        MqttConnectFlags,
        MqttDisconnectFlags,
        MqttMessage,
        MqttModule,
        MqttReasonCode,
    )

logger = logging.getLogger("entropy_hunt.mesh")


class MeshError(RuntimeError):
    pass


class MeshConnectionError(MeshError):
    pass


class MeshPublishError(MeshError):
    pass


@dataclass(frozen=True, slots=True)
class MeshEnvelope:
    topic: str
    payload: dict[str, Any]
    timestamp_ms: int
    sender_id: str = "local"
    message_id: str = ""
    hmac_sig: str = ""


@dataclass(frozen=True, slots=True)
class MeshSubscription:
    subscriber_id: str
    topic_pattern: str


def encode_envelope(envelope: MeshEnvelope) -> bytes:
    return (json.dumps(asdict(envelope), separators=(",", ":")) + "\n").encode("utf-8")


def decode_envelope(packet: bytes) -> MeshEnvelope:
    try:
        payload = json.loads(packet.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("malformed envelope payload") from exc
    try:
        return MeshEnvelope(
            topic=str(payload["topic"]),
            payload=dict(payload["payload"]),
            timestamp_ms=int(payload["timestamp_ms"]),
            sender_id=str(payload["sender_id"]),
            message_id=str(payload["message_id"]),
            hmac_sig=str(payload.get("hmac_sig", "")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"malformed envelope fields: {exc}") from exc


_MESH_SECRET_RAW = os.environ.get("ENTROPYHUNT_MESH_SECRET", "")
_MESH_SECRET = _MESH_SECRET_RAW.encode() if _MESH_SECRET_RAW else b""


def _require_secret() -> bytes:
    if not _MESH_SECRET:
        raise OSError("ENTROPYHUNT_MESH_SECRET must be set and non-empty")
    return _MESH_SECRET


def _envelope_hmac_data(envelope: MeshEnvelope) -> bytes:
    payload_json = json.dumps(envelope.payload, sort_keys=True, separators=(",", ":"))
    return (
        f"{envelope.topic}:{envelope.sender_id}:{envelope.message_id}:{envelope.timestamp_ms}:{payload_json}"
    ).encode()


def sign_envelope(envelope: MeshEnvelope) -> MeshEnvelope:
    data = _envelope_hmac_data(envelope)
    sig = _hmac.new(_require_secret(), data, _hashlib.sha256).hexdigest()
    return MeshEnvelope(
        topic=envelope.topic,
        payload=envelope.payload,
        timestamp_ms=envelope.timestamp_ms,
        sender_id=envelope.sender_id,
        message_id=envelope.message_id,
        hmac_sig=sig,
    )


def verify_envelope(envelope: MeshEnvelope) -> bool:
    if not _MESH_SECRET:
        return True
    if not envelope.hmac_sig:
        return False
    data = _envelope_hmac_data(envelope)
    expected = _hmac.new(_require_secret(), data, _hashlib.sha256).hexdigest()
    return _hmac.compare_digest(envelope.hmac_sig, expected)


def _matches_topic(topic_pattern: str, topic: str) -> bool:
    if topic_pattern.endswith("#"):
        return topic.startswith(topic_pattern[:-1])
    return topic == topic_pattern


DEFAULT_MESSAGE_CAP = 10_000

_DISCOVERY_GROUP = "239.255.0.1"
_DISCOVERY_PORT = 9002
_DISCOVERY_INTERVAL = 5.0
_DISCOVERY_TTL = 2


@runtime_checkable
class MeshBusProtocol(Protocol):
    peer_id: str

    def subscribe(self, subscriber_id: str, topic_pattern: str) -> None:
        ...

    def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        timestamp_ms: int,
        sender_id: str | None = ...,
        message_id: str | None = ...,
    ) -> MeshEnvelope:
        ...

    def poll(
        self,
        subscriber_id: str | None = ...,
        *,
        topic_pattern: str | None = ...,
    ) -> list[MeshEnvelope]:
        ...

    def history(self, topic: str) -> list[MeshEnvelope]:
        ...

    def latest(self, topic: str) -> MeshEnvelope | None:
        ...

    def count(self) -> int:
        ...

    def close(self) -> None:
        ...


class InMemoryMeshBus(MeshBusProtocol):
    def __init__(self, *, peer_id: str = "local", message_cap: int = DEFAULT_MESSAGE_CAP) -> None:
        self.peer_id = peer_id
        self._messages: dict[str, list[MeshEnvelope]] = defaultdict(list)
        self._sequence = 0
        self._subscriptions: dict[str, list[MeshSubscription]] = defaultdict(list)
        self._inboxes: dict[str, deque[MeshEnvelope]] = defaultdict(deque)
        self._message_cap = message_cap
        self._notify = threading.Event()
        self._inbox_locks: dict[str, threading.Lock] = {}
        self._messages_lock = threading.Lock()

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
        with self._messages_lock:
            topic_messages = self._messages[envelope.topic]
            topic_messages.append(envelope)
            if len(topic_messages) > self._message_cap:
                evicted = topic_messages[: len(topic_messages) - self._message_cap]
                del topic_messages[: len(topic_messages) - self._message_cap]
                logger.debug(
                    "evicted %d messages from topic %s (cap=%d)",
                    len(evicted),
                    envelope.topic,
                    self._message_cap,
                )
        for subscriber_id, subscriptions in self._subscriptions.items():
            if any(
                _matches_topic(subscription.topic_pattern, envelope.topic)
                for subscription in subscriptions
            ):
                lock = self._inbox_locks.setdefault(subscriber_id, threading.Lock())
                with lock:
                    inbox = self._inboxes[subscriber_id]
                    inbox.append(envelope)
                    while len(inbox) > self._message_cap:
                        inbox.popleft()
        self._notify.set()
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
            ),
        )

    def poll(
        self,
        subscriber_id: str | None = None,
        *,
        topic_pattern: str | None = None,
    ) -> list[MeshEnvelope]:
        if subscriber_id is None:
            return []
        self._notify.clear()
        lock = self._inbox_locks.setdefault(subscriber_id, threading.Lock())
        with lock:
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
            inbox.clear()
            inbox.extend(remaining)
            return matched

    def history(self, topic: str) -> list[MeshEnvelope]:
        with self._messages_lock:
            return list(self._messages.get(topic, []))

    def latest(self, topic: str) -> MeshEnvelope | None:
        with self._messages_lock:
            messages = self._messages.get(topic, [])
            return messages[-1] if messages else None

    def count(self) -> int:
        with self._messages_lock:
            return sum(len(messages) for messages in self._messages.values())

    def close(self) -> None:
        return


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


class VertexMeshBus(InMemoryMeshBus):
    def __init__(
        self,
        *,
        peer_id: str = "vertex",
        helper_bin: str | None = None,
        strict: bool = False,
    ) -> None:
        super().__init__(peer_id=peer_id)
        self.helper_bin = helper_bin or os.environ.get(
            "ENTROPYHUNT_VERTEX_HELPER",
            str(
                Path(os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()))
                / "warmup-vertex-rust"
                / "target"
                / "debug"
                / "node",
            ),
        )
        self.bridge: Any | None = None
        self._warning: str | None = None
        self._stall_count: int = 0
        self._stall_fallback_threshold: int = 3
        self._strict: bool = strict
        self.active_mode = "real"
        _bridge_cls = importlib.import_module("core.bridge").VertexBridge

        keypair_path = os.environ.get("ENTROPYHUNT_VERTEX_KEYPAIR", "submission/vertex.key")
        peer_addr = os.environ.get("ENTROPYHUNT_VERTEX_PEER", "127.0.0.1:9000")
        if not Path(self.helper_bin).exists():
            if strict:
                _msg = (
                    f"VertexMeshBus helper binary not found at {self.helper_bin!r}. "
                    "The --mesh real flag was set, so falling back to in-process "
                    "bus is not allowed.  Install the helper or remove --mesh real."
                )
                raise MeshConnectionError(_msg)
            logger.warning("VertexMeshBus helper binary is missing; falling back to in-process bus")
            self._warning = (
                "VertexMeshBus helper binary is missing; "
                "publish calls will fall back to the in-process bus only."
            )
            self.active_mode = "stub"
            return
        try:
            self.bridge = _bridge_cls(
                binary_path=self.helper_bin,
                keypair_path=keypair_path,
                peer_addr=peer_addr,
            )
            confirmed = self.bridge.wait_confirmed(timeout=2.0)
            if not confirmed or self.bridge.proc.poll() is not None:
                detail = self.bridge.last_error()
                if strict:
                    _msg = (
                        f"VertexMeshBus bridge helper exited before publish "
                        f"(strict mode). Detail: {detail}"
                    )
                    raise MeshConnectionError(_msg)
                self.active_mode = "stub"
                self._warning = (
                    "VertexMeshBus bridge helper exited before publish; "
                    f"falling back to in-process delivery. Detail: {detail}"
                )
        except (OSError, subprocess.SubprocessError) as exc:
            if strict:
                _msg = f"VertexMeshBus bridge startup failed (strict mode): {exc}"
                raise MeshConnectionError(_msg) from exc
            logger.warning("VertexMeshBus bridge blocked by helper startup mismatch: %s", exc)
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
                logger.warning(self._warning)
                self._warning = None
            return envelope
        if not self.bridge.publish(topic, payload):
            self._stall_count += 1
            detail = self.bridge.last_error()
            logger.warning(
                "VertexMeshBus publish failed (stall #%d, detail=%s)",
                self._stall_count,
                detail,
            )
            if self._stall_count >= self._stall_fallback_threshold:
                logger.warning(
                    "VertexMeshBus stall count (%d) exceeded threshold (%d); "
                    "switching to in-process bus for remainder of session",
                    self._stall_count,
                    self._stall_fallback_threshold,
                )
                self.active_mode = "stub"
                if self._warning is None:
                    self._warning = (
                        f"VertexMeshBus publish stalled {self._stall_count} times; "
                        f"switching to in-process bus only. detail={detail}"
                    )
                self.bridge.close()
                self.bridge = None
        else:
            self._stall_count = 0
        return envelope

    def close(self) -> None:
        if self.bridge is not None:
            self.bridge.close()


@dataclass
class LocalPeerConfig:
    bind_host: str = ""
    bind_port: int = 0
    peer_addresses: list[tuple[str, int]] | None = None
    publish_min_interval: float | None = None
    discovery_enabled: bool = False
    discovery_group: str = ""
    discovery_port: int = 0


class LocalPeerMeshBus(InMemoryMeshBus):
    DEFAULT_PUBLISH_MIN_INTERVAL: float = 0.0

    def __init__(self, *, peer_id: str, config: LocalPeerConfig | None = None) -> None:
        cfg = config or LocalPeerConfig()
        bind_host = cfg.bind_host
        bind_port = cfg.bind_port
        peer_addresses = cfg.peer_addresses
        publish_min_interval = cfg.publish_min_interval
        super().__init__(peer_id=peer_id)
        resolved_bind_host = bind_host or os.environ.get("ENTROPYHUNT_HOST", "127.0.0.1")
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((resolved_bind_host, bind_port))
        self._socket.setblocking(False)
        self._bind_host, self._bind_port = self._socket.getsockname()
        self._peer_addresses = list(peer_addresses or [])
        self._peers_lock = threading.Lock()
        self._seen_message_ids: set[str] = set()
        self._seen_order: deque[str] = deque()
        self._seen_ids_cap = DEFAULT_MESSAGE_CAP
        self._publish_min_interval: float = (
            publish_min_interval
            if publish_min_interval is not None
            else self.DEFAULT_PUBLISH_MIN_INTERVAL
        )
        self._last_publish_time: float = 0.0
        self._discovery_enabled = cfg.discovery_enabled
        self._discovery_group = (
            cfg.discovery_group
            or os.environ.get("ENTROPYHUNT_DISCOVERY_GROUP", _DISCOVERY_GROUP)
        )
        self._discovery_port = (
            cfg.discovery_port
            or int(os.environ.get("ENTROPYHUNT_DISCOVERY_PORT", str(_DISCOVERY_PORT)))
        )
        self._discovery_socket: socket.socket | None = None
        self._discovery_thread: threading.Thread | None = None
        self._discovery_stop = threading.Event()
        self._discovered_peers: dict[str, tuple[str, int]] = {}
        self._discovery_lock = threading.Lock()
        self._discovery_nonce = secrets.token_hex(8)
        self._hello_interval = _DISCOVERY_INTERVAL
        if self._discovery_enabled:
            self.start_discovery()

    @property
    def bind_address(self) -> tuple[str, int]:
        return (self._bind_host, self._bind_port)

    def set_peers(self, peer_addresses: list[tuple[str, int]]) -> None:
        with self._peers_lock:
            self._peer_addresses = list(peer_addresses)

    def start_discovery(self) -> None:
        if self._discovery_thread is not None:
            return
        try:
            self._discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._discovery_socket.bind(("", self._discovery_port))
            mreq = socket.inet_aton(self._discovery_group) + socket.inet_aton("0.0.0.0")
            self._discovery_socket.setsockopt(
                socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq,
            )
            self._discovery_socket.setsockopt(
                socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, _DISCOVERY_TTL,
            )
            self._discovery_socket.settimeout(1.0)
        except OSError as exc:
            logger.warning("LocalPeerMeshBus discovery bind failed: %s", exc)
            self._discovery_socket = None
            return
        self._discovery_thread = threading.Thread(target=self._discovery_loop, daemon=True)
        self._discovery_thread.start()

    def stop_discovery(self) -> None:
        self._discovery_stop.set()
        if self._discovery_thread is not None:
            self._discovery_thread.join(timeout=2.0)
            self._discovery_thread = None
        if self._discovery_socket is not None:
            with contextlib.suppress(OSError):
                self._discovery_socket.close()
            self._discovery_socket = None

    def _discovery_loop(self) -> None:
        last_hello = 0.0
        while not self._discovery_stop.is_set():
            now = time.monotonic()
            if now - last_hello >= self._hello_interval:
                self._send_hello()
                last_hello = now
            self._recv_hello()
            time.sleep(0.1)

    def _send_hello(self) -> None:
        if self._discovery_socket is None:
            return
        advertised_host = self._bind_host if self._bind_host not in ("", "0.0.0.0") else "127.0.0.1"
        packet = json.dumps({
            "type": "HELLO",
            "peer_id": self.peer_id,
            "address": advertised_host,
            "port": self._bind_port,
            "nonce": self._discovery_nonce,
        }).encode("utf-8")
        try:
            self._discovery_socket.sendto(
                packet, (self._discovery_group, self._discovery_port),
            )
        except OSError as exc:
            logger.debug("Discovery HELLO send failed: %s", exc)

    def _recv_hello(self) -> None:
        if self._discovery_socket is None:
            return
        try:
            packet, _addr = self._discovery_socket.recvfrom(2048)
        except (BlockingIOError, TimeoutError, OSError):
            return
        try:
            data = json.loads(packet.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        if data.get("type") == "HELLO":
            remote_peer_id = data.get("peer_id")
            remote_address = data.get("address")
            remote_port = data.get("port")
            remote_nonce = data.get("nonce")
            if (
                remote_peer_id
                and remote_peer_id != self.peer_id
                and remote_address
                and isinstance(remote_port, int)
                and remote_nonce != self._discovery_nonce
            ):
                with self._peers_lock:
                    key = (remote_address, remote_port)
                    if key not in self._peer_addresses:
                        self._peer_addresses.append(key)
                with self._discovery_lock:
                    self._discovered_peers[remote_peer_id] = (remote_address, remote_port)
                logger.info(
                    "Discovered peer %s at %s:%d", remote_peer_id, remote_address, remote_port,
                )

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
        self._seen_order.append(envelope.message_id)
        if len(self._seen_order) > self._seen_ids_cap:
            evicted_id = self._seen_order.popleft()
            self._seen_message_ids.discard(evicted_id)
        if self._publish_min_interval > 0:
            now = time.monotonic()
            elapsed = now - self._last_publish_time
            if elapsed < self._publish_min_interval:
                logger.debug(
                    "LocalPeerMeshBus publish to %s rate-limited (%.1fms < %.1fms min)",
                    topic,
                    elapsed * 1000,
                    self._publish_min_interval * 1000,
                )
                return envelope
            self._last_publish_time = now
        encoded = encode_envelope(envelope)
        with self._peers_lock:
            peers = list(self._peer_addresses)
        for host, port in peers:
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
            self._seen_order.append(envelope.message_id)
            if len(self._seen_order) > self._seen_ids_cap:
                evicted_id = self._seen_order.popleft()
                self._seen_message_ids.discard(evicted_id)
            self._remember(envelope)
            incoming.append(envelope)
        if subscriber_id is None:
            return incoming
        return super().poll(subscriber_id, topic_pattern=topic_pattern)

    def close(self) -> None:
        self.stop_discovery()
        self._socket.close()


@dataclass
class FoxMQConfig:
    mqtt_host: str = ""
    mqtt_port: int = 1884
    username: str | None = None
    password: str | None = None
    client_id: str | None = None
    lazy_connect: bool = False
    publish_min_interval: float | None = None


class FoxMQMeshBus(InMemoryMeshBus):
    _RECONNECT_BACKOFF_BASE = 1.0
    _RECONNECT_BACKOFF_MAX = 30.0
    _RECONNECT_MAX_ATTEMPTS = 10
    _MQTT_RC_SUCCESS: int = 0

    DEFAULT_PUBLISH_MIN_INTERVAL: float = 0.0

    def __init__(self, *, peer_id: str, config: FoxMQConfig | None = None) -> None:
        cfg = config or FoxMQConfig()
        mqtt_host = cfg.mqtt_host
        mqtt_port = cfg.mqtt_port
        username = cfg.username
        password = cfg.password
        client_id = cfg.client_id
        lazy_connect = cfg.lazy_connect
        publish_min_interval = cfg.publish_min_interval
        super().__init__(peer_id=peer_id)
        self._seen_message_ids: set[str] = set()
        self._seen_order: deque[str] = deque()
        self._seen_ids_cap = DEFAULT_MESSAGE_CAP
        self._mqtt_host = mqtt_host or os.environ.get("ENTROPYHUNT_MQTT_HOST", "127.0.0.1")
        self._mqtt_port = mqtt_port
        self._mqtt_username = username
        self._mqtt_password = password
        self._mqtt_client_id = client_id or peer_id
        self._mqtt_module: Any = None
        self._client: Any = None
        self._connected = threading.Event()
        self._lazy_connect: bool = bool(lazy_connect)
        self._reconnect_attempts: int = 0
        self._reconnect_scheduled: bool = False
        self._reconnect_timer: threading.Timer | None = None
        self._closing = False
        self._seen_lock = threading.Lock()
        self._publish_min_interval: float = (
            publish_min_interval
            if publish_min_interval is not None
            else self.DEFAULT_PUBLISH_MIN_INTERVAL
        )
        self._last_publish_time: float = 0.0
        try:
            mqtt_module = importlib.import_module("paho.mqtt.client")
        except ModuleNotFoundError:
            logger.warning(
                "paho-mqtt not installed; FoxMQMeshBus will not connect until connect() is called",
            )
            self._import_error: MeshConnectionError | None = MeshConnectionError(
                "FoxMQMeshBus requires the optional 'paho-mqtt' package. "
                "Install it before using --transport foxmq.",
            )
            return
        self._import_error = None
        self._init_mqtt(_cast("MqttModule", mqtt_module))
        if not self._lazy_connect:
            self.connect()

    def _init_mqtt(self, mqtt_module: MqttModule) -> None:
        self._mqtt_module = mqtt_module
        _protocol = getattr(mqtt_module, "MQTTv5", getattr(mqtt_module, "MQTTv311", None))
        _client_kwargs: dict = {
            "callback_api_version": mqtt_module.CallbackAPIVersion.VERSION2,
            "client_id": self._mqtt_client_id,
        }
        if _protocol is not None:
            _client_kwargs["protocol"] = _protocol
        self._client = mqtt_module.Client(**_client_kwargs)
        if self._mqtt_username is not None or self._mqtt_password is not None:
            self._client.username_pw_set(username=self._mqtt_username, password=self._mqtt_password)
        self._client.on_message = self._on_message
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

    def connect(self, *, _timeout: float = 0.5) -> None:
        if self._connected.is_set():
            return
        if self._import_error is not None:
            try:
                mqtt_module = importlib.import_module("paho.mqtt.client")
            except ModuleNotFoundError:
                raise self._import_error from None
            self._import_error = None
            self._init_mqtt(_cast("MqttModule", mqtt_module))
        if self._client is None:
            _msg = "FoxMQMeshBus: MQTT client not initialized"
            raise RuntimeError(_msg)
        try:
            self._client.connect(self._mqtt_host, self._mqtt_port)
        except (OSError, ConnectionError) as exc:
            logger.warning(
                "FoxMQMeshBus connect failed to %s:%d: %s",
                self._mqtt_host,
                self._mqtt_port,
                exc,
            )
            _msg = f"FoxMQMeshBus connect failed to {self._mqtt_host}:{self._mqtt_port}: {exc}"
            raise MeshConnectionError(_msg) from exc
        self._client.loop_start()
        deadline = time.monotonic() + _timeout
        while not self._connected.is_set() and time.monotonic() < deadline:
            time.sleep(0.02)
        if not self._connected.is_set():
            self._connected.set()
            self._client.subscribe("swarm/#")
        self._reconnect_attempts = 0
        logger.info("FoxMQMeshBus connected to %s:%d", self._mqtt_host, self._mqtt_port)

    def _on_connect(
        self,
        _client: MqttClient | None,
        _userdata: object,
        _flags: MqttConnectFlags,
        reason_code: MqttReasonCode,
        _properties: object = None,
    ) -> None:
        rc = int(reason_code.value)
        if rc == self._MQTT_RC_SUCCESS:
            self._connected.set()
            self._reconnect_attempts = 0
            if _client is not None:
                _client.subscribe("swarm/#")
            logger.info(
                "FoxMQMeshBus MQTT connection established to %s:%d",
                self._mqtt_host,
                self._mqtt_port,
            )
        else:
            self._connected.clear()
            logger.warning(
                "FoxMQMeshBus MQTT connect refused (rc=%d), will attempt reconnect",
                rc,
            )

    def _on_disconnect(
        self,
        _client: MqttClient | None,
        _userdata: object,
        _flags: MqttDisconnectFlags,
        reason_code: MqttReasonCode,
        _properties: object = None,
    ) -> None:
        self._connected.clear()
        rc = int(reason_code.value)
        if rc != self._MQTT_RC_SUCCESS and not self._closing:
            logger.warning(
                "FoxMQMeshBus unexpected disconnect from %s:%d (rc=%d), scheduling reconnect",
                self._mqtt_host,
                self._mqtt_port,
                rc,
            )
            self._schedule_reconnect()
        else:
            logger.info(
                "FoxMQMeshBus cleanly disconnected from %s:%d",
                self._mqtt_host,
                self._mqtt_port,
            )

    def _schedule_reconnect(self) -> None:
        if self._reconnect_attempts >= self._RECONNECT_MAX_ATTEMPTS:
            logger.error(
                "FoxMQMeshBus exceeded max reconnect attempts (%d) to %s:%d",
                self._RECONNECT_MAX_ATTEMPTS,
                self._mqtt_host,
                self._mqtt_port,
            )
            return
        if self._reconnect_scheduled:
            return
        self._reconnect_scheduled = True
        backoff = min(
            self._RECONNECT_BACKOFF_BASE * (2**self._reconnect_attempts),
            self._RECONNECT_BACKOFF_MAX,
        )
        self._reconnect_attempts += 1
        logger.info(
            "FoxMQMeshBus reconnect attempt %d/%d in %.1fs",
            self._reconnect_attempts,
            self._RECONNECT_MAX_ATTEMPTS,
            backoff,
        )

        def _do_reconnect() -> None:
            self._reconnect_scheduled = False
            self._reconnect_timer = None
            try:
                if self._client is not None and not self._closing:
                    self._client.reconnect()
                    logger.info(
                        "FoxMQMeshBus reconnected to %s:%d",
                        self._mqtt_host,
                        self._mqtt_port,
                    )
            except (OSError, ConnectionError) as exc:
                logger.warning("FoxMQMeshBus reconnect failed: %s", exc)
                self._schedule_reconnect()

        self._reconnect_timer = threading.Timer(backoff, _do_reconnect)
        self._reconnect_timer.daemon = True
        self._reconnect_timer.start()

    def _on_message(
        self, _client: MqttClient | None, _userdata: object, message: MqttMessage,
    ) -> None:
        try:
            envelope = decode_envelope(message.payload)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            logger.warning("FoxMQMeshBus: malformed payload received, dropping")
            return
        if not verify_envelope(envelope):
            logger.warning(
                "FoxMQMeshBus: invalid HMAC on message from %s, dropping", envelope.sender_id,
            )
            return
        with self._seen_lock:
            if envelope.message_id in self._seen_message_ids:
                return
        self._remember(envelope)
        with self._seen_lock:
            self._seen_message_ids.add(envelope.message_id)
            self._seen_order.append(envelope.message_id)
            if len(self._seen_order) > self._seen_ids_cap:
                evicted_id = self._seen_order.popleft()
                self._seen_message_ids.discard(evicted_id)

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
        with self._seen_lock:
            self._seen_message_ids.add(envelope.message_id)
            self._seen_order.append(envelope.message_id)
            if len(self._seen_order) > self._seen_ids_cap:
                evicted_id = self._seen_order.popleft()
                self._seen_message_ids.discard(evicted_id)
        if self._client is not None and self._connected.is_set():
            if self._publish_min_interval > 0:
                now = time.monotonic()
                elapsed = now - self._last_publish_time
                if elapsed < self._publish_min_interval:
                    logger.debug(
                        "FoxMQMeshBus publish to %s rate-limited (%.1fms < %.1fms min)",
                        topic,
                        elapsed * 1000,
                        self._publish_min_interval * 1000,
                    )
                    return envelope
                self._last_publish_time = now
            try:
                self._client.publish(topic, encode_envelope(sign_envelope(envelope)), qos=1)
            except (OSError, ConnectionError, RuntimeError) as exc:
                logger.warning("FoxMQMeshBus publish to %s failed: %s", topic, exc)
                self._connected.clear()
                self._schedule_reconnect()
                _msg = f"FoxMQMeshBus publish to {topic} failed: {exc}"
                raise MeshPublishError(_msg) from exc
        else:
            logger.debug(
                "FoxMQMeshBus publish to %s while disconnected — retained locally only",
                topic,
            )
        return envelope

    def poll(
        self,
        subscriber_id: str | None = None,
        *,
        topic_pattern: str | None = None,
    ) -> list[MeshEnvelope]:
        if subscriber_id is None:
            return []
        return super().poll(subscriber_id, topic_pattern=topic_pattern)

    def close(self) -> None:
        self._closing = True
        if self._reconnect_timer is not None:
            self._reconnect_timer.cancel()
            self._reconnect_timer = None
        if self._client is not None:
            if self._connected.is_set():
                self._client.disconnect()
                self._client.loop_stop()
            self._connected.clear()
            self._client = None
