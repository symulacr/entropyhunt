from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MeshMessage:
    topic: str
    payload: dict[str, Any]
    timestamp_ms: int


class MeshBus:
    def __init__(self) -> None:
        self._messages: dict[str, list[MeshMessage]] = defaultdict(list)

    def publish(self, topic: str, payload: dict[str, Any], *, timestamp_ms: int) -> MeshMessage:
        message = MeshMessage(topic=topic, payload=payload, timestamp_ms=timestamp_ms)
        self._messages[topic].append(message)
        return message

    def history(self, topic: str) -> list[MeshMessage]:
        return list(self._messages.get(topic, []))

    def latest(self, topic: str) -> MeshMessage | None:
        messages = self._messages.get(topic, [])
        return messages[-1] if messages else None

    def count(self) -> int:
        return sum(len(messages) for messages in self._messages.values())
