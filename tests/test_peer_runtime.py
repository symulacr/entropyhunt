from __future__ import annotations

import socket

from simulation.peer_protocol import PeerEndpoint
from simulation.peer_runtime import PeerRuntime, PeerRuntimeConfig


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _make_runtime(peer_id: str, port: int, peers: tuple[PeerEndpoint, ...]) -> PeerRuntime:
    runtime = PeerRuntime(
        PeerRuntimeConfig(
            peer_id=peer_id,
            port=port,
            peers=peers,
            grid=3,
            duration=6,
            tick_seconds=1,
            target=(1, 1),
            search_increment=0.5,
            completion_certainty=0.9,
        )
    )
    for cell in runtime.certainty_map:
        runtime.certainty_map.set_certainty(cell.coordinate, 1.0, updated_by="test", now_ms=0)
    runtime.certainty_map.set_certainty((1, 1), 0.5, updated_by="test", now_ms=0)
    return runtime


def test_peer_runtime_exchanges_heartbeats_claims_and_survivor_events() -> None:
    port_1 = _free_port()
    port_2 = _free_port()
    peers_1 = (PeerEndpoint("drone_2", "127.0.0.1", port_2),)
    peers_2 = (PeerEndpoint("drone_1", "127.0.0.1", port_1),)
    runtime_1 = _make_runtime("drone_1", port_1, peers_1)
    runtime_2 = _make_runtime("drone_2", port_2, peers_2)
    runtime_1.local_drone.position = (0, 1)
    runtime_2.local_drone.position = (2, 1)

    try:
        runtime_1.bootstrap()
        runtime_2.bootstrap()
        for _ in range(6):
            runtime_1.tick()
            runtime_2.tick()
        assert "drone_2" in runtime_1.peer_drones
        assert runtime_1.peer_drones["drone_2"].alive is True
        assert runtime_1.bft._round_id >= 1
        assert runtime_2.bft._round_id >= 1
        assert runtime_1.certainty_map.cell((1, 1)).certainty > 0.5
        assert runtime_2.certainty_map.cell((1, 1)).certainty > 0.5
        assert runtime_1.survivor_found is True
        assert runtime_2.survivor_found is True
    finally:
        runtime_1.mesh.close()
        runtime_2.mesh.close()
