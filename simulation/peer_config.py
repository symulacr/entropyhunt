
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from simulation.base_config import BaseSimulationConfig

if TYPE_CHECKING:
    from simulation.protocol import PeerEndpoint

_DEFAULT_STALE_TIMEOUT_TICK_MULTIPLIER = 20
_DEFAULT_TARGET_FORCE_AT_S = 100

class PeerFailureError(RuntimeError):

    def __init__(self, message: str, *, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code

@dataclass(frozen=True, slots=True, kw_only=True)
class PeerRuntimeConfig(BaseSimulationConfig):

    peer_id: str
    host: str = os.environ.get("ENTROPYHUNT_HOST", "127.0.0.1")
    port: int = 0
    peers: tuple[PeerEndpoint, ...] = ()
    transport: str = "local"
    mqtt_host: str = os.environ.get("ENTROPYHUNT_MQTT_HOST", "127.0.0.1")
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    tick_delay_seconds: float | None = None
    stale_timeout_tick_multiplier: int = _DEFAULT_STALE_TIMEOUT_TICK_MULTIPLIER
    target_force_at_s: int = _DEFAULT_TARGET_FORCE_AT_S
    fail_at: int | None = None
    failure_mode: str = "crash"
    final_map_path: str = ""
    map_publish_interval: int = 2
    control_file: str = ""
    control_port: int = 0
    packet_loss: float = 0.0
    jitter_ms: float = 0.0
    discovery_enabled: bool = True
