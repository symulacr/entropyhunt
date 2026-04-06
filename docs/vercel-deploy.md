# Vercel Deployment Guide

This project now ships as a static shell built into `dist/`.

## Prerequisites
- Bun 1.3.10+
- Node 18+ (for the Vercel CLI / `npx`)
- Python 3.12+
- a Vercel account and project

## First-time setup
1. Run `bun run build` locally to confirm the packaged shell builds.
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
   pytest -q
   node --test entropy_hunt_ui.test.mjs
   ruff check .
   mypy .
   bun run build
   ```
3. Walk through `docs/frontend-qa-checklist.md`.
4. Run `bun run deploy:preview`.
5. Promote with `bun run deploy:prod` when the preview looks correct.

## Notes
- The deployment is still a static/demo surface; it does not create live Vertex/FoxMQ connectivity.
- If the build output directory changes, update `package.json`, `vercel.json`, and the deployment tests together.
