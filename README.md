# Entropy Hunt

Entropy Hunt is a deterministic swarm-search demo for the Vertex Swarm Challenge Track 2 brief.

Today the repo is best used as a **local demo + replay/inspection project**, not as production ops software.

## Supported lanes

| Surface / command | Use it for | Current status |
| --- | --- | --- |
| `bun run hunt` | main local multi-process demo path with OpenTUI monitor | best-supported operator/demo path |
| `python3 main.py --mode stub` | source-level debugging and artifact generation | backup debug/demo lane |
| `dist/console.html` / `entropy_hunt_v2.html` | replay inspection and optional local snapshot polling | experimental browser inspector |
| `bun run build` | packaged static replay/share shell | supported static packaging path |
| ROS 2 / Webots / Vertex / FoxMQ lanes | bring-up and integration work | experimental only |

## Quick start

### 1) Install local tooling

```bash
bun install
```

Python 3 is still required underneath for the swarm runtime.

### 2) Run the main local demo

```bash
bun run hunt
```

This launches:
- the Python peer runtime
- the local snapshot server
- the OpenTUI monitor

Useful variants:

```bash
bun run hunt -- --no-monitor
bun run hunt:monitor
bun run hunt:stress:peers
bun run hunt:stress:grid
bun run hunt:clean
```

### 3) Generate replay artifacts

```bash
python3 main.py --final-map final_map.json --final-html entropy_hunt_final.html --svg-map entropy_hunt_final.svg
```

Outputs:
- `final_map.json` — replay payload
- `entropy_hunt_final.html` — static final-state snapshot
- `entropy_hunt_final.svg` — heatmap SVG

### 4) Serve local live snapshots to the browser inspector

```bash
bun run hunt:serve
```

This exposes:
- `http://127.0.0.1:8765/snapshot.json`
- `http://127.0.0.1:8765/state.json`
- `http://127.0.0.1:8765/events.json`

### 5) Build and preview the static shell

```bash
bun run build
bun run preview
```

`dist/` ships one packaged browser surface:
- `dist/index.html` — static landing shell
- `dist/console.html` — experimental replay/live inspector

`entropy_hunt_mockup.html` remains source-only and is not deployed.

### 6) Deploy the static shell

See:
- `docs/frontend-qa-checklist.md`
- `docs/vercel-deploy.md`

## Verification

```bash
pytest -q tests/test_deployment_config.py tests/test_frontend_build.py tests/test_live_runtime_server.py tests/test_live_runtime_control.py
node --test entropy_hunt_ui.test.mjs
ruff check tests/test_deployment_config.py tests/test_frontend_build.py tests/test_live_runtime_server.py tests/test_live_runtime_control.py
mypy tests/test_deployment_config.py tests/test_frontend_build.py tests/test_live_runtime_server.py tests/test_live_runtime_control.py scripts/serve_live_runtime.py scripts/build_frontend.py
```

## Current boundaries

- **Peer runtime (`bun run hunt`)** is the main local-demo path.
- **Browser surfaces** are replay/inspection tools with synthetic/demo affordances; they are not production operator consoles.
- **Stub mode** is useful for debugging and artifact generation, but it is not the main operator story.
- **ROS 2, Webots, Vertex, and FoxMQ** remain experimental bring-up lanes and should not be described as parity-grade ports here.
- **Static packaging** is for replay/share workflows, not live mesh deployment.

## Core files

- `main.py` — CLI entrypoint
- `simulation/stub.py` — single-process demo runtime
- `simulation/peer_runtime.py` — multi-process peer runtime
- `scripts/run_local_peers.py` — local peer launcher
- `scripts/serve_live_runtime.py` — local snapshot HTTP server
- `dashboard/tui_monitor_v2.ts` — OpenTUI monitor
- `entropy_hunt_v2.html` — browser replay/live inspector
- `scripts/build_frontend.py` — static shell build step

## Docs kept on purpose

- `docs/frontend-qa-checklist.md` — manual release/deploy QA for the packaged shell
- `docs/vercel-deploy.md` — deployment contract for the static shell

These stay because they directly support build, release, and operator-facing verification work.
