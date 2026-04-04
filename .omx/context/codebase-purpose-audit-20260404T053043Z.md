# Context Snapshot — codebase-purpose-audit

- Timestamp: 2026-04-04T05:30:43Z
- Task statement: Discover the codebase, its purpose, and assess completeness score, gaps, limits, and risks.
- Desired outcome: A clear brownfield audit that explains what exists, what it is for, what is missing, and how risky it is to rely on as-is.
- Stated solution: Use deep-interview to clarify the evaluation target before handing off to planning/execution.
- Probable intent hypothesis: The user wants an evidence-backed repo audit to decide whether this project is submission-ready or needs more work.

## Known facts / evidence
- Python project `entropy-hunt` describes itself as a deterministic entropy-driven swarm search simulation (`pyproject.toml`).
- Main runnable entrypoint is `main.py`, which runs `simulation.stub.EntropyHuntSimulation` and prints an ASCII heatmap plus JSON summary.
- Core modules exist for certainty map, zone selection, BFT coordination, heartbeat tracking, mesh bus, claim coordination, and ASCII visualization (`core/*`, `roles/*`, `auction/protocol.py`, `viz/heatmap.py`).
- Tests pass: `pytest -q` => 8 passed; `node --test entropy_hunt_ui.test.mjs` => 6 passed; `ruff check .` and `mypy .` both pass.
- `entropy_hunt.md` is a large hackathon handoff/spec that describes a broader target system including Vertex/FoxMQ, optional Webots, failure injector, richer heatmap, and demo expectations.
- Current repo also includes two standalone HTML prototypes (`entropy_hunt_mockup.html`, `entropy_hunt_v2.html`) that are described in the markdown as prototypes rather than production implementation.
- Default simulation run succeeds but only reports 0.59 coverage after 180 seconds in `final_map.json`, while the handoff doc suggests full coverage should be achievable.

## Constraints
- Read-only discovery/audit mode for now; no implementation should happen in deep-interview.
- Completeness scoring is ambiguous because the repo contains multiple targets: Python stub, UI prototypes, and broader hackathon spec.

## Unknowns / open questions
- What baseline should the completeness score use?
- Is the desired deliverable a submission-readiness audit, a code-quality audit, or a product/feature completeness audit?
- Should the HTML prototypes count as part of the deliverable or be treated strictly as throwaway references?

## Decision-boundary unknowns
- Whether OMX should score against the markdown handoff spec, the runnable Python stub only, or the combined repo narrative.
- Whether gaps should be prioritized for demo readiness, production readiness, or architecture fidelity.

## Likely codebase touchpoints
- `main.py`
- `simulation/stub.py`
- `core/*.py`
- `roles/*.py`
- `auction/protocol.py`
- `viz/heatmap.py`
- `tests/*.py`
- `entropy_hunt.md`
- `entropy_hunt_v2.html`, `entropy_hunt_mockup.html`
