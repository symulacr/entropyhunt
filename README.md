# Entropy Hunt

Entropy Hunt is a deterministic swarm-search demo for the Vertex Swarm Challenge Track 2 brief. Treat this repo as a local demo + replay/inspection project, not production ops software.

## Commands

```bash
bun install
bun run hunt
bun run hunt:serve
bun run build
bun run preview
python3 main.py --final-map final_map.json --final-html entropy_hunt_final.html --svg-map entropy_hunt_final.svg
```

## Verification

```bash
pytest -q tests/test_deployment_config.py tests/test_frontend_build.py tests/test_live_runtime_server.py tests/test_live_runtime_control.py
node --test entropy_hunt_ui.test.mjs
ruff check tests/test_deployment_config.py tests/test_frontend_build.py tests/test_live_runtime_server.py tests/test_live_runtime_control.py
mypy tests/test_deployment_config.py tests/test_frontend_build.py tests/test_live_runtime_server.py tests/test_live_runtime_control.py scripts/serve_live_runtime.py scripts/build_frontend.py
```

## Caveats

- `bun run hunt` is the main supported local-demo path.
- `python3 main.py --mode stub` is a backup debug/artifact lane.
- `dist/console.html` / `entropy_hunt_v2.html` are experimental replay/live inspectors.
- `entropy_hunt_mockup.html` is source-only and not deployed.
- ROS 2, Webots, Vertex, and FoxMQ lanes remain experimental.
