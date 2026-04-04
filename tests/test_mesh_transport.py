from __future__ import annotations

import socket
import time

from core.mesh import LocalPeerMeshBus


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def test_local_peer_mesh_bus_exchanges_messages_between_ports() -> None:
    port_a = _free_port()
    port_b = _free_port()
    bus_a = LocalPeerMeshBus(peer_id="drone_1", bind_port=port_a, peer_addresses=[("127.0.0.1", port_b)])
    bus_b = LocalPeerMeshBus(peer_id="drone_2", bind_port=port_b, peer_addresses=[("127.0.0.1", port_a)])
    try:
        bus_a.publish("swarm/test", {"value": 7}, timestamp_ms=100)
        received = []
        for _ in range(10):
            received = bus_b.poll()
            if received:
                break
            time.sleep(0.01)
        assert received
        envelope = received[0]
        assert envelope.topic == "swarm/test"
        assert envelope.payload == {"value": 7}
        assert envelope.sender_id == "drone_1"
        assert bus_b.latest("swarm/test") == envelope
    finally:
        bus_a.close()
        bus_b.close()
