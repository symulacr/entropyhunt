# Frontend QA Checklist

Use this checklist before sharing or deploying the packaged Entropy Hunt shell.

## Preconditions
- `python3 main.py --final-map final_map.json --svg-map final_map.svg --final-html final_map.html`
- `bun run build`
- `bun run preview`

## Landing shell (`dist/index.html`)
- [ ] Page loads without missing CSS or broken links.
- [ ] Summary cards match the latest `final_map.json` values.
- [ ] Snapshot preview renders the exported SVG.
- [ ] Links to `console.html`, `mockup.html`, and `artifacts/final_map.html` open correctly.

## Rich console (`dist/console.html`)
- [ ] Default load shows synthetic demo mode.
- [ ] **Load replay** accepts `dist/artifacts/final_map.json`.
- [ ] Mode chip flips from `synthetic demo` to `replay snapshot`.
- [ ] Coverage/BFT/dropout metrics match the replay payload.
- [ ] **Clear replay** restores or reloads back to synthetic mode.

## Minimal mockup (`dist/mockup.html`)
- [ ] Loads without console errors.
- [ ] **Load replay** accepts `dist/artifacts/final_map.json`.
- [ ] Replay state updates metrics and event log.

## Artifact checks
- [ ] `dist/artifacts/final_map.json` exists and is downloadable.
- [ ] `dist/artifacts/final_map.svg` opens as a standalone image.
- [ ] `dist/artifacts/final_map.html` opens as a standalone snapshot.

## Deployment smoke checks
- [ ] Vercel/static host serves `dist/index.html` as the root page.
- [ ] Static links remain relative and work on preview URLs.
- [ ] No page implies live Vertex/FoxMQ integration.
