# Frontend QA Checklist

Use this checklist before sharing or deploying the packaged Entropy Hunt static shell. The browser outputs are replay/demo surfaces, not production live-ops tooling.

## Preconditions
- `python3 main.py --final-map final_map.json --svg-map final_map.svg --final-html final_map.html`
- `bun run build`
- `bun run preview`

## Landing shell (`dist/index.html`)
- [ ] Page loads without missing CSS or broken links.
- [ ] Summary cards match the latest `final_map.json` values.
- [ ] Snapshot preview renders the exported SVG.
- [ ] Links to `console.html`, `mockup.html`, and `artifacts/final_map.html` open correctly.

## Rich console (`dist/console.html`, experimental browser inspector)
- [ ] Default load shows synthetic demo mode.
- [ ] **Load replay** accepts `dist/artifacts/final_map.json`.
- [ ] Mode chip flips from `synthetic demo` to `replay snapshot`.
- [ ] Coverage/BFT/dropout metrics match the replay payload.
- [ ] **Clear replay** restores or reloads back to synthetic mode.
- [ ] Live polling is only exercised when the local helpers are running (`bun run live:peers` and `bun run live:serve`).
- [ ] The page copy/presentation does not imply a production-ready or parity-grade live operator surface.

## Minimal mockup (`dist/mockup.html`, prototype replay surface)
- [ ] Loads without console errors.
- [ ] **Load replay** accepts `dist/artifacts/final_map.json`.
- [ ] Replay state updates metrics and event log.
- [ ] The page is still framed as a mockup/prototype rather than an authoritative operator UI.

## Artifact checks
- [ ] `dist/artifacts/final_map.json` exists and is downloadable.
- [ ] `dist/artifacts/final_map.svg` opens as a standalone image.
- [ ] `dist/artifacts/final_map.html` opens as a standalone snapshot.

## Deployment smoke checks
- [ ] Vercel/static host serves `dist/index.html` as the root page.
- [ ] Static links remain relative and work on preview URLs.
- [ ] No page implies live Vertex/FoxMQ integration without the local helper scripts.
- [ ] README / deploy notes shipped with the release still describe ROS, Webots, and Vertex/FoxMQ as experimental or bring-up lanes.
