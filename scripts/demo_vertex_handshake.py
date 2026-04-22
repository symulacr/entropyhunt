from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.mesh import FoxMQConfig, FoxMQMeshBus

STALE_AFTER_S = 3.0
HEARTBEAT_INTERVAL = 0.8

_MESH_SECRET_STR = os.environ.get("ENTROPYHUNT_MESH_SECRET")
if _MESH_SECRET_STR is None:
    raise RuntimeError("ENTROPYHUNT_MESH_SECRET environment variable is required")
HMAC_SECRET = _MESH_SECRET_STR.encode()


def _sign(payload: dict) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(HMAC_SECRET, data, hashlib.sha256).hexdigest()


class Peer:
    __slots__ = ("_bus", "_peers", "_running", "_thread", "peer_id")

    def __init__(self, peer_id: str, mqtt_host: str, mqtt_port: int) -> None:
        self.peer_id = peer_id
        self._bus = FoxMQMeshBus(
            peer_id=peer_id,
            config=FoxMQConfig(mqtt_host=mqtt_host, mqtt_port=mqtt_port, lazy_connect=True),
        )
        self._bus.subscribe(peer_id, "swarm/#")
        self._peers: dict[str, float] = {}
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._bus.connect()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name=f"peer-{self.peer_id}")
        self._thread.start()
        self._send_hello()
        logger.info("[%s] started", self.peer_id)

    def stop(self) -> None:
        self._running = False
        self._bus.close()
        logger.info("[%s] stopped", self.peer_id)

    def _send_hello(self) -> None:
        payload = {"type": "HELLO", "peer_id": self.peer_id}
        payload["sig"] = _sign(payload)
        self._bus.publish(
            "swarm/hello", payload, timestamp_ms=int(time.time() * 1000), sender_id=self.peer_id,
        )

    def _send_heartbeat(self) -> None:
        payload = {"type": "HEARTBEAT", "peer_id": self.peer_id}
        payload["sig"] = _sign(payload)
        self._bus.publish(
            "swarm/heartbeat",
            payload,
            timestamp_ms=int(time.time() * 1000),
            sender_id=self.peer_id,
        )

    def _loop(self) -> None:
        last_hb = time.monotonic()
        while self._running:
            now = time.monotonic()
            for env in self._bus.poll(self.peer_id):
                src = env.payload.get("peer_id", env.sender_id)
                if src == self.peer_id:
                    continue
                msg_type = env.payload.get("type", "")
                if msg_type in ("HELLO", "HEARTBEAT"):
                    sig_received = env.payload.pop("sig", None)
                    expected = _sign(env.payload)
                    env.payload["sig"] = sig_received
                    if sig_received != expected:
                        logger.info("[%s] BAD signature from %s — ignored", self.peer_id, src)
                        continue
                    was_known = src in self._peers
                    self._peers[src] = now
                    if not was_known:
                        logger.info("[%s] discovered peer %s via %s", self.peer_id, src, msg_type)
                    elif msg_type == "HELLO":
                        logger.info("[%s] peer %s rejoined (HELLO received)", self.peer_id, src)

            for pid, last_seen in list(self._peers.items()):
                if now - last_seen > STALE_AFTER_S:
                    logger.info(
                        "[%s] peer %s is STALE (no heartbeat for %ss)",
                        self.peer_id,
                        pid,
                        STALE_AFTER_S,
                    )
                    del self._peers[pid]

            if now - last_hb >= HEARTBEAT_INTERVAL:
                self._send_heartbeat()
                last_hb = now

            time.sleep(0.1)

    @property
    def known_peers(self) -> list[str]:
        return list(self._peers)


def run_demo(mqtt_host: str, mqtt_port: int) -> None:
    logger.info(
        "\n=== Vertex/FoxMQ Warm-Up Handshake Demo (broker %s:%s) ===\n",
        mqtt_host,
        mqtt_port,
    )

    alpha = Peer("alpha", mqtt_host, mqtt_port)
    beta = Peer("beta", mqtt_host, mqtt_port)

    alpha.start()
    beta.start()
    time.sleep(1.5)

    logger.info("\n--- Phase 1: both peers online ---")
    time.sleep(2.0)
    logger.info("  alpha knows: %s", alpha.known_peers)
    logger.info("  beta  knows: %s", beta.known_peers)

    logger.info("\n--- Phase 2: beta goes offline (simulated) ---")
    beta.stop()
    time.sleep(STALE_AFTER_S + 1.5)
    logger.info("  alpha knows: %s  (beta should be stale/removed)", alpha.known_peers)

    logger.info("\n--- Phase 3: beta comes back ---")
    beta2 = Peer("beta", mqtt_host, mqtt_port)
    beta2.start()
    time.sleep(2.0)
    logger.info("  alpha knows: %s  (beta should be rediscovered)", alpha.known_peers)
    logger.info("  beta  knows: %s", beta2.known_peers)

    logger.info("\n--- Teardown ---")
    alpha.stop()
    beta2.stop()
    logger.info("\nDemo complete. ✓")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="FoxMQ Warm-Up Stateful Handshake demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1884)
    args = parser.parse_args()
    run_demo(args.host, args.port)


if __name__ == "__main__":
    main()
