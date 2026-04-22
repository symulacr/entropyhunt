
from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING, Any

from core.mesh import MeshBusProtocol, MeshEnvelope

if TYPE_CHECKING:
    from simulation.proof import ProofLogger

_rng = random.Random()

class NetworkInjector(MeshBusProtocol):

    def __init__(
        self,
        bus: MeshBusProtocol,
        *,
        packet_loss: float = 0.0,
        jitter_ms: float = 0.0,
        proof_logger: ProofLogger | None = None,
    ) -> None:
        self._bus = bus
        self._packet_loss = max(0.0, min(1.0, packet_loss))
        self._jitter_ms = max(0.0, jitter_ms)
        self._proof_logger = proof_logger
        self.peer_id: str = bus.peer_id

    def subscribe(self, subscriber_id: str, topic_pattern: str) -> None:
        self._bus.subscribe(subscriber_id, topic_pattern)

    def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        timestamp_ms: int,
        sender_id: str | None = None,
        message_id: str | None = None,
    ) -> MeshEnvelope:
        if self._packet_loss > 0.0 and _rng.random() < self._packet_loss:
            if self._proof_logger is not None:
                self._proof_logger.log(
                    timestamp_ms // 1000,
                    "packet_dropped",
                    f"dropped publish to {topic}",
                    topic=topic,
                    peer_id=self.peer_id,
                )
            return MeshEnvelope(
                topic=topic,
                payload=payload,
                timestamp_ms=timestamp_ms,
                sender_id=sender_id or self.peer_id,
                message_id=message_id or "",
            )
        kwargs: dict[str, Any] = {"timestamp_ms": timestamp_ms}
        if sender_id is not None:
            kwargs["sender_id"] = sender_id
        if message_id is not None:
            kwargs["message_id"] = message_id
        return self._bus.publish(topic, payload, **kwargs)

    def poll(
        self,
        subscriber_id: str | None = None,
        *,
        topic_pattern: str | None = None,
    ) -> list[MeshEnvelope]:
        if self._jitter_ms > 0.0:
            time.sleep(_rng.uniform(0.0, self._jitter_ms / 1000.0))
        messages = self._bus.poll(subscriber_id, topic_pattern=topic_pattern)
        if self._packet_loss <= 0.0:
            return messages
        kept: list[MeshEnvelope] = []
        for msg in messages:
            if _rng.random() < self._packet_loss:
                if self._proof_logger is not None:
                    self._proof_logger.log(
                        msg.timestamp_ms // 1000,
                        "packet_dropped",
                        f"dropped polled message on {msg.topic}",
                        topic=msg.topic,
                        peer_id=self.peer_id,
                    )
            else:
                kept.append(msg)
        return kept

    def history(self, topic: str) -> list[MeshEnvelope]:
        return self._bus.history(topic)

    def latest(self, topic: str) -> MeshEnvelope | None:
        return self._bus.latest(topic)

    def count(self) -> int:
        return self._bus.count()

    def close(self) -> None:
        self._bus.close()
