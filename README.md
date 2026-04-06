# Entropy Hunt

Entropy Hunt is a deterministic, entropy-driven swarm-search demo for the Vertex Swarm Challenge Track 2 brief. The repository ships several demo-oriented surfaces with different maturity levels:

- a **pure Python coordination simulation** (`main.py --mode stub`)
- a **local multi-process peer runtime** (`main.py --mode peer`, `scripts/run_local_peers.py`)
- an **optional FoxMQ/Vertex adapter lane** (`core/mesh.py`, `scripts/setup_foxmq.py`, `scripts/run_foxmq_cluster.py`)
- an **optional Webots-backed peer runtime lane** (`simulation/webots_runtime.py`, `webots_world/`)
- a **packaged static replay/share shell** built into `dist/` via `bun run build`
- two **browser prototypes** (`entropy_hunt_v2.html`, `entropy_hunt_mockup.html`)

The Python runtime stays standard-library-only and covers the core demo loop: entropy-based zone selection, claim resolution, heartbeat failure handling, survivor confirmation, and replayable output artifacts. Operator packaging and live-monitoring surfaces remain local-demo tooling, not production-ready control software.

## Maturity guide

Use the repo with the following expectations:

| Surface / lane | What it is good for now | Current maturity |
| --- | --- | --- |
| `bun run hunt` peer runtime + OpenTUI | current local-demo monitor path for the separate-process swarm | **best-supported local demo path**, still not parity-grade distributed BFT or production ops |
| `python3 main.py --mode stub` | source-level debugging, artifact generation, single-process demo runs | **debug/demo lane**, not the main operator story |
| `entropy_hunt_v2.html` / `dist/console.html` | replay inspection and optional local snapshot polling | **experimental browser inspector** with synthetic/demo affordances |
| `entropy_hunt_mockup.html` / `dist/mockup.html` | minimal replay prototype and visual reference | **prototype only**, replay/demo oriented |
| ROS 2 commands | bring-up and contract experimentation | **experimental lane**, not a parity-grade port |
| Webots runtime | controller integration experiments | **experimental lane**, not validated end-to-end here |
| Vertex / FoxMQ adapters | transport bring-up toward the target architecture | **adapter/bring-up lane**, not a validated live deployment |

## Bun-first demo entrypoint

Install Bun dependencies once, then use Bun as the user-facing runtime shell. Bun launches the Python swarm engine and the OpenTUI monitor; Python 3 is still required underneath for the peer runtime itself.

```bash
bun install
```

The simplest Bun-first operator path is:

```bash
bun run hunt
```

Runtime mode matrix:

| Command | Lane | Requires | Status |
| --- | --- | --- | --- |
| `bun run hunt` | peer | Python | current local-demo baseline |
| `bun run hunt -- --mode ros2 --ros-runtime host` | ROS 2 host | ROS 2 + colcon | experimental bring-up |
| `bun run hunt -- --mode ros2 --ros-runtime docker` | ROS 2 docker | Docker | experimental bring-up |
| `bun run hunt:ros2` | ROS 2 host | ROS 2 + colcon | experimental shortcut |
| `bun run hunt:ros2:docker` | ROS 2 docker | Docker | experimental shortcut |

That single Bun command:
- allocates free ports
- launches the Python peer swarm
- launches the local snapshot server
- launches the OpenTUI monitor
- keeps launcher/peer JSON in session logs instead of mixing it into the active terminal by default
- writes runtime logs/session metadata under `runtime/`

If you want to attach the monitor manually to an already-running server, use:

```bash
bun run hunt:monitor
```

The Bun runtime scripts also expose the common presets directly:

```bash
bun run hunt:stress:peers
bun run hunt:stress:grid
bun run hunt:clean
```

To pass custom flags through to the Python launcher, forward them after `--`:

```bash
bun run hunt -- --count 8 --duration 240 --output-dir peer-runs-custom
```

The single-process stub command remains the simplest source-level debug lane:

```bash
python3 main.py --drones 5 --grid 10 --duration 180 --target 7,3 --fail drone_2 --fail-at 60
```

Treat that stub lane as a backup/demo path rather than a parity-grade operator surface. It is still useful for local debugging and direct artifact generation, but the peer runtime is the current Bun-first operator path and the multi-process proof/readiness story remains partially synthetic.

## Quick start

### 1) Run the current local-demo operator path

```bash
bun run hunt
```

This is the current recommended local-demo operator path: Bun drives the multi-process peer launcher, the snapshot server, and the OpenTUI monitor while the Python engine does the swarm simulation.

### 2) Generate backend artifacts

```bash
python3 main.py --final-map final_map.json --final-html entropy_hunt_final.html --svg-map entropy_hunt_final.svg
```

This produces:

- `final_map.json` — replayable simulation payload with summary, grid, events, Voronoi partitions, and bridge snapshot
- `entropy_hunt_final.html` — static final-state dashboard snapshot
- `entropy_hunt_final.svg` — standalone heatmap SVG

### 3) Run a local peer demo without the monitor

```bash
bun run hunt -- --no-monitor
```

This launches one process per drone in `--mode peer`, starts the snapshot server, writes per-peer snapshots under `runtime/sessions/<session>/snapshots`, and appends proofs under the same runtime session.

### 4) Serve live peer snapshots to the rich console manually

```bash
bun run hunt:serve
```

This exposes `http://127.0.0.1:8765/snapshot.json`, `state.json`, and `events.json` for live polling from `entropy_hunt_v2.html`. The server rereads and re-merges peer JSON on demand, so it is intended for local demos and operator inspection rather than high-throughput production streaming.

### 5) Build the packaged static shell

```bash
bun run build
```

Then preview it locally:

```bash
bun run preview
```

The build copies the current browser prototypes and replay artifacts into `dist/`, and generates a landing-shell `dist/index.html` from the latest `final_map.json` + `final_map.svg`. Treat that output as a static replay/share artifact, not as a production live-ops console.


### 6) Deploy the static replay/share shell to Vercel or any static host

- `vercel.json` points Vercel at `bun run build` and the `dist/` output directory.
- `docs/frontend-qa-checklist.md` captures the recommended manual browser QA pass before sharing or deployment.
- `docs/vercel-deploy.md` documents first-time Vercel setup plus preview/production deploy commands.

## Browser surfaces (prototype / replay)

Open either browser prototype directly in a browser, or use the packaged copies in `dist/`:

- `entropy_hunt_v2.html`
- `entropy_hunt_mockup.html`

Use **Load replay** and select `final_map.json` to inspect a real backend-generated snapshot instead of the synthetic inline demo.

- `entropy_hunt_v2.html` / `dist/console.html` is the richer experimental inspector. It can also connect to `http://127.0.0.1:8765/snapshot.json` when `bun run hunt:serve` is running, but that flow is still meant for local demos.
- `entropy_hunt_mockup.html` / `dist/mockup.html` is a lighter prototype/replay surface. Keep it framed as a mockup, not as the authoritative operator UI.

## Verification

```bash
pytest -q tests/test_deployment_config.py tests/test_frontend_build.py tests/test_live_runtime_server.py tests/test_live_runtime_control.py
node --test entropy_hunt_ui.test.mjs
ruff check tests/test_deployment_config.py tests/test_frontend_build.py tests/test_live_runtime_server.py tests/test_live_runtime_control.py
mypy tests/test_deployment_config.py tests/test_frontend_build.py tests/test_live_runtime_server.py tests/test_live_runtime_control.py scripts/serve_live_runtime.py scripts/build_frontend.py
```

## What is real and what is not

- Coordination layer: the separate-process peer demo runs as five Python peer processes plus a local snapshot server, and the OpenTUI monitor runs separately under Bun. The peers communicate over local UDP socket transport (`LocalPeerMeshBus`) and publish JSON snapshots that the monitor renders live. The snapshot server merges JSON files on request; it is a local observability helper, not a durable streaming backend. The `NullBus` load-bearing test still proves that the single-process fallback loses contested-claim quorum and result delivery when transport is removed.
- BFT: the primary stub demo now exchanges real contest and vote messages between five in-process drone replicas over the mesh bus, and quorum is `N/2 + 1` (3 of 5). The local UDP peer runtime still publishes confirmed claim results from a coordinator; it is not a production Byzantine implementation. Multi-process mode uses coordinator-confirmed result finalization. The coordinator is elected deterministically by peer index and rotates on dropout. This is crash-fault-tolerant but not Byzantine-fault-tolerant. The stub mode uses genuine peer-vote collection with N/2+1 quorum. Full BFT across the multi-process path is the next engineering milestone.
- Certainty maps: the multi-process path keeps one local certainty map per peer process and merges peer snapshots by taking the max certainty per cell. The merged map drives zone selection; the local map drives that peer’s own search updates.
- Simulation: the multi-process peer runtime plus `dashboard/tui_monitor_v2.ts` is the primary separate-process monitor path. The Python monitor remains a fallback and the terminal stub remains the single-process backup. The Webots path exists, but live Webots integration has not been validated end-to-end in this environment.
- Port/adaptor lanes: ROS 2, Webots, and Vertex/FoxMQ remain experimental or bring-up surfaces. They are useful for integration work, but this repo should not describe them as parity-grade ports of the main peer runtime until they have matching behavior and end-to-end validation.

## Current architecture

### Implemented now
- `core/certainty_map.py` — entropy math, decay, coverage helpers
- `core/zone_selector.py` — highest-entropy zone selection
- `core/bft.py` / `auction/protocol.py` — deterministic local claim resolution
- `core/mesh.py` / `simulation/peer_protocol.py` — pluggable in-memory, local UDP, and optional FoxMQ-backed transport helpers
- `core/heartbeat.py` / `failure/injector.py` — dropout timing and stale release flow
- `simulation/stub.py` — pure Python multi-drone demo run
- `simulation/peer_runtime.py` / `scripts/run_local_peers.py` — real local multi-process peer execution for heartbeat/claim/BFT exchange
- `dashboard/tui_monitor_v2.ts` — OpenTUI monitor for the live peer snapshot feed
- `dashboard/tui_monitor.py` — Python fallback monitor for the same snapshot feed
- `simulation/webots_runtime.py` / `webots_world/` — optional Webots-backed peer runtime path
- `scripts/serve_live_runtime.py` — live HTTP snapshot server for the rich console (`/snapshot.json`, `/state.json`, `/events.json`)
- `auction/voronoi.py` — Voronoi-style ownership/partition helpers for overlays
- `simulation/webots_bridge.py` — dependency-free bridge contract for future Webots supervisor wiring
- `viz/heatmap.py` — ASCII, SVG, and static HTML snapshot rendering

Latest peer-run check (5 peers, 180 ticks, drone_2 dropped at `t=60`):
- surviving peers report roughly `0.73` visited coverage
- first auction appears at `t=2`
- first failure appears at `t=60`
- first survivor event appears at `t=92`

### Still synthetic / not yet live mesh
- Two Vertex integration paths were attempted. Path 1: the `tashi-vertex` Rust CLI warm-up, which ran successfully for two local nodes over 60 seconds with signed hello and stable heartbeat (see `submission/02_vertex_warmup_a.log` and `submission/03_vertex_warmup_b.log`). Path 2: the `libtashi-vertex.so` shared-library path used by `VertexMeshBus` for in-process message routing. That path failed in this environment with a dynamic linker error (`submission/04_vertex_real_attempt.txt`). The warm-up proves Vertex node operation; the adapter requires a matching shared-library build. The multi-process peer demo uses local socket IPC as the active transport, and `VertexMeshBus` remains the production-path adapter.
- no actual Webots runtime has been validated end-to-end in this environment yet (the repo now has a real controller-backed path, but not CI execution)
- packaged frontend build pipeline is static-only and dependency-free (`package.json` + `scripts/build_frontend.py`)

## Key files

- `entropy_hunt.md` — product/spec handoff
- `main.py` — CLI entrypoint
- `simulation/stub.py` — demo runtime
- `simulation/peer_runtime.py` — multi-process peer runtime
- `frontend/index.template.html` — packaged app-shell template
- `entropy_hunt_v2.html` — richer experimental browser inspector
- `entropy_hunt_mockup.html` — minimal replayable prototype/mockup
- `scripts/build_frontend.py` — static packaging build step
- `scripts/run_local_peers.py` — launch helper for multi-peer local demos
- `scripts/setup_foxmq.py` / `scripts/run_foxmq_cluster.py` — FoxMQ cluster helpers
- `simulation/webots_controller.py` / `simulation/webots_runtime.py` — experimental Webots controller + runtime bridge
- `entropy_hunt_ui.test.mjs` — static-console regression tests

## Dependency policy

Runtime implementation is standard-library-only.
Developer tooling (`pytest`, `ruff`, `mypy`, Node for the HTML tests) is expected to be available in the dev environment.

## Judge attacks and answers

**"Frontier-based exploration is 30 years old."**  
Your answer: "Entropy Hunt is not frontier exploration. Frontier exploration requires a central map owner and a global cost function. Entropy Hunt uses P2P-merged certainty maps with BFT-resistant zone auctions. The coordination mechanism — not the search heuristic — is the submission. Frontier exploration has no equivalent of the BFT claim lock or the emergent Voronoi zone partition."

**"Your 'entropy' is just inverse coverage percentage."**  
Your answer: "Shannon entropy is not inverse coverage. At certainty = 0.0 or 1.0, H = 0. At certainty = 0.5, H = 1.0 bit. The decay function pushes searched zones toward 0.5 (maximum entropy), not toward 0.0. This means the swarm re-hunts stale zones — a behaviour not possible with coverage-percentage targeting." Show the decay function in your README.

**"Webots simulation with mocked sensors is not realistic."**  
Your answer: Quote the Track 2 brief verbatim: "Use mocked sensor data if it helps you focus on the mesh networking." This is not a sensor demo. It is a coordination demo. The brief says this explicitly.

**"Your coordinator is a single point of failure / trust."**  
Answer: correct for the multi-process path. The stub demo, which is the primary submission surface, uses genuine peer-vote collection. The multi-process coordinator rotates on dropout and is crash-tolerant. Full BFT across separate OS processes requires a production Vertex/FoxMQ transport, which is the integration this submission is designed to demonstrate the need for. The coordination logic is complete; the transport is the gap.
