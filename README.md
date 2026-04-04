# Entropy Hunt

Entropy Hunt is a deterministic, entropy-driven swarm-search demo for the Vertex Swarm Challenge Track 2 brief. The repository now ships three aligned surfaces:

- a **pure Python coordination simulation** (`main.py` -> `simulation/stub.py`)
- two **static operator consoles** (`entropy_hunt_v2.html`, `entropy_hunt_mockup.html`)
- a **dependency-free bridge contract** for future Webots integration (`simulation/webots_bridge.py`)

The implementation stays CI-friendly and standard-library-only while still covering the core demo loop: entropy-based zone selection, BFT-style claim resolution, heartbeat failure handling, survivor confirmation, and replayable output artifacts.

## Quick start

```bash
python3 main.py --final-map final_map.json --final-html entropy_hunt_final.html --svg-map entropy_hunt_final.svg
```

This produces:

- `final_map.json` — replayable simulation payload with summary, grid, events, Voronoi partitions, and bridge snapshot
- `entropy_hunt_final.html` — static final-state dashboard snapshot
- `entropy_hunt_final.svg` — standalone heatmap SVG

## Frontend replay

Open either static console in a browser:

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
- `core/heartbeat.py` / `failure/injector.py` — dropout timing and stale release flow
- `simulation/stub.py` — pure Python multi-drone demo run
- `auction/voronoi.py` — Voronoi-style ownership/partition helpers for overlays
- `simulation/webots_bridge.py` — dependency-free bridge contract for future Webots supervisor wiring
- `viz/heatmap.py` — ASCII, SVG, and static HTML snapshot rendering

### Still synthetic / not yet live mesh
- no real Vertex/FoxMQ transport
- no actual Webots runtime dependency wired in
- no packaged frontend build pipeline

## Key files

- `entropy_hunt.md` — product/spec handoff
- `main.py` — CLI entrypoint
- `simulation/stub.py` — demo runtime
- `entropy_hunt_v2.html` — richer operator console
- `entropy_hunt_mockup.html` — minimal replayable mockup
- `entropy_hunt_ui.test.mjs` — static-console regression tests

## Dependency policy

Runtime implementation is standard-library-only.
Developer tooling (`pytest`, `ruff`, `mypy`, Node for the HTML tests) is expected to be available in the dev environment.
