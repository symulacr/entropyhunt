# Vercel Deployment Guide

This project ships as a static replay/share shell built into `dist/`.

## Prerequisites
- Bun 1.3.10+
- Node 18+
- Python 3.12+
- a Vercel account and project

## First-time setup
1. Run `bun run build` locally to confirm the packaged static shell builds.
2. Run `npx vercel@latest` once and follow the prompts to link the local folder to a Vercel project.
3. Confirm `vercel.json` still points Vercel at:
   - `buildCommand`: `bun run build`
   - `outputDirectory`: `dist`

## One-command deploys

### Preview deploy
```bash
bun run deploy:preview
```

### Production deploy
```bash
bun run deploy:prod
```

Both commands rebuild the static shell locally before invoking the Vercel CLI.

## Recommended release flow
1. Regenerate backend artifacts:
   ```bash
   python3 main.py --final-map final_map.json --svg-map final_map.svg --final-html final_map.html
   ```
2. Run verification:
   ```bash
   pytest -q tests/test_deployment_config.py tests/test_frontend_build.py tests/test_live_runtime_server.py tests/test_live_runtime_control.py
   node --test entropy_hunt_ui.test.mjs
   ruff check tests/test_deployment_config.py tests/test_frontend_build.py tests/test_live_runtime_server.py tests/test_live_runtime_control.py
   mypy tests/test_deployment_config.py tests/test_frontend_build.py tests/test_live_runtime_server.py tests/test_live_runtime_control.py scripts/serve_live_runtime.py scripts/build_frontend.py
   bun run build
   ```
3. Walk through `docs/frontend-qa-checklist.md`.
4. Run `bun run deploy:preview`.
5. Promote with `bun run deploy:prod` when the preview looks correct.

## Notes
- The deployed output is still a static/demo surface; it does not create live Vertex/FoxMQ connectivity.
- `dist/console.html` is an experimental browser inspector; it is the only packaged browser surface and should not be presented as a production operator console.
- `entropy_hunt_mockup.html` remains source-only for prototype/reference use and is not part of the packaged deploy surface.
- Live console polling still depends on local helper scripts such as `bun run live:peers` and `bun run live:serve`.
- If the build output directory or packaging command changes, update `package.json`, `vercel.json`, and the deployment tests together.
