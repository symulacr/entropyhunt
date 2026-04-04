# Entropy Hunt

Entropy Hunt is a deterministic, entropy-driven swarm-search demo for the Vertex Swarm Challenge Track 2 brief. The repository now ships five aligned surfaces:

- a **pure Python coordination simulation** (`main.py --mode stub`)
- a **local multi-process peer runtime** (`main.py --mode peer`, `scripts/run_local_peers.py`)
- a **packaged static app shell** built into `dist/` via `npm run build`
- two **static operator consoles** (`entropy_hunt_v2.html`, `entropy_hunt_mockup.html`)
- a **dependency-free bridge contract** for future Webots integration (`simulation/webots_bridge.py`)

The implementation stays CI-friendly and standard-library-only while still covering the core demo loop: entropy-based zone selection, BFT-style claim resolution, heartbeat failure handling, survivor confirmation, and replayable output artifacts.

## Quick start

### 1) Generate backend artifacts

```bash
python3 main.py --final-map final_map.json --final-html entropy_hunt_final.html --svg-map entropy_hunt_final.svg
```

This produces:

- `final_map.json` — replayable simulation payload with summary, grid, events, Voronoi partitions, and bridge snapshot
- `entropy_hunt_final.html` — static final-state dashboard snapshot
- `entropy_hunt_final.svg` — standalone heatmap SVG

### 2) Run a local peer demo

```bash
python3 scripts/run_local_peers.py --count 5 --duration 30 --output-dir peer-runs
```

This launches one process per drone in `--mode peer` using the local UDP mesh transport and writes one JSON snapshot per peer.

### 3) Build the packaged frontend shell

```bash
npm run build
```

Then preview it locally:

```bash
npm run preview
```

The build copies the current consoles and replay artifacts into `dist/`, and generates a landing-shell `dist/index.html` from the latest `final_map.json` + `final_map.svg`.


### 4) Deploy to Vercel or any static host

- `vercel.json` points Vercel at `npm run build` and the `dist/` output directory.
- `docs/frontend-qa-checklist.md` captures the recommended manual browser QA pass before sharing or deployment.
- `docs/vercel-deploy.md` documents first-time Vercel setup plus preview/production deploy commands.

## Frontend replay

Open either static console directly in a browser, or use the packaged copies in `dist/`:

- `entropy_hunt_v2.html`
- `entropy_hunt_mockup.html`

Then use **Load replay** and select `final_map.json` to inspect a real backend-generated snapshot instead of the synthetic inline demo.

## Verification

```bash
pytest -q
node --test entropy_hunt_ui.test.mjs
ruff check .
mypy .
```

## Current architecture

### Implemented now
- `core/certainty_map.py` — entropy math, decay, coverage helpers
- `core/zone_selector.py` — highest-entropy zone selection
- `core/bft.py` / `auction/protocol.py` — deterministic local claim resolution
- `core/mesh.py` / `simulation/peer_protocol.py` — pluggable in-memory + local UDP peer transport
- `core/heartbeat.py` / `failure/injector.py` — dropout timing and stale release flow
- `simulation/stub.py` — pure Python multi-drone demo run
- `simulation/peer_runtime.py` / `scripts/run_local_peers.py` — real local multi-process peer execution for heartbeat/claim/BFT exchange
- `auction/voronoi.py` — Voronoi-style ownership/partition helpers for overlays
- `simulation/webots_bridge.py` — dependency-free bridge contract for future Webots supervisor wiring
- `viz/heatmap.py` — ASCII, SVG, and static HTML snapshot rendering

### Still synthetic / not yet live mesh
- no real Vertex/FoxMQ transport (the current live path is local UDP peer transport only)
- no actual Webots runtime dependency wired in
- packaged frontend build pipeline is static-only and dependency-free (`package.json` + `scripts/build_frontend.py`)

## Key files

- `entropy_hunt.md` — product/spec handoff
- `main.py` — CLI entrypoint
- `simulation/stub.py` — demo runtime
- `simulation/peer_runtime.py` — multi-process peer runtime
- `frontend/index.template.html` — packaged app-shell template
- `entropy_hunt_v2.html` — richer operator console
- `entropy_hunt_mockup.html` — minimal replayable mockup
- `scripts/build_frontend.py` — static packaging build step
- `scripts/run_local_peers.py` — launch helper for multi-peer local demos
- `entropy_hunt_ui.test.mjs` — static-console regression tests

## Dependency policy

Runtime implementation is standard-library-only.
Developer tooling (`pytest`, `ruff`, `mypy`, Node for the HTML tests) is expected to be available in the dev environment.
