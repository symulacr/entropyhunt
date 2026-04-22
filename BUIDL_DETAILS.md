# BUIDL Details — Entropy Hunt

## What It Is

Entropy Hunt is a search-and-rescue drone swarm coordination system for the Vertex Swarm Challenge 2026, Track 2.

It deploys multiple autonomous agents over disaster terrain, partitions search zones via Voronoi cells, resolves conflicts through Byzantine-fault-tolerant consensus, and continues the mission when up to 30% of the fleet drops out. Every coordination decision is cryptographically signed and auditable.

## Core Stack

| Layer | Tech | Responsibility |
|---|---|---|
| Frontend | HTML/CSS/JS | Mission control dashboard, live telemetry SSE stream |
| TUI Monitor | TypeScript / Bun | Terminal dashboard (launched via `--tui`) |
| Core Engine | Python 3.12+ | BFT consensus, Voronoi auction, mesh buses, inline TUI, failure injection |
| Mesh Bridge | Rust / tokio / axum | HMAC endpoints, UDP multicast relay, peer registry, HTTP health API |
| Simulation | Webots / ROS2 | Physics-based drone validation, middleware topic bridge |

## Key Features

- Autonomous terrain partitioning — Voronoi cells allocate zones per drone without central coordinator
- BFT consensus — Zone conflicts resolved via quorum voting with cryptographic proof emission
- 4 transport buses — In-memory, UDP peer-to-peer, FoxMQ MQTT, and Vertex UDP multicast (via `--mesh real`)
- Failure resilience — Packet loss injection, drone dropout simulation, graceful peer recovery
- Observable — Browser dashboards, terminal TUI, signed JSONL proof logs, HTML artifacts
- Multi-language — Python engine, Rust mesh bridge, TypeScript operator monitor

## How to Run

```bash
./setup.sh          # install deps (Python, Rust, Bun)
cp .env.example .env
# edit .env — set ENTROPYHUNT_MESH_SECRET
./demo.sh           # 60s swarm demo
./demo.sh --tui     # with terminal dashboard
```

## Architecture

```
Operator / TUI / Frontend
        ↓ HTTP / SSE
Core Engine (Python) — consensus.py, auction/, mesh.py
        ↓ subprocess / UDP
Vertex Bridge (Rust) — HMAC sign, UDP multicast, peer heartbeat
        ↓ ROS2 topics
Webots / ROS2 simulation nodes
```

## Track Alignment

| Requirement | Implementation |
|---|---|
| Autonomous terrain partitioning | `auction/voronoi.py` generates drone-specific zones |
| BFT consensus | `core/consensus.py` resolves conflicting claims via quorum |
| 30% failure resilience | `failure/network_injector.py` + `--packet-loss 0.3` demo |
| Cryptographic audit trail | `scripts/verify_poc.py` verifies signed `proofs.jsonl` |
| P2P mesh transport | `core/mesh.py` — LocalPeer, FoxMQ, VertexMesh buses |
| ROS2 middleware bridge | `ros2_ws/` publishes consensus to QoS topics |
| Webots integration | `simulation/webots_controller.py` drives physics drones |
| Multi-language stack | Python + Rust + TypeScript |

## What Makes It Different

- Every zone claim is voted on by peers and signed with HMAC-SHA256
- Every failure (packet loss, dropout) is injected deterministically and recovered from
- Every run produces replayable artifacts (`proofs.jsonl`, final maps, HTML snapshots)
- The TUI renders the live consensus state — not just drone positions
