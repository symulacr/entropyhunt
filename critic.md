# Entropy Hunt Critic Report

## Shared Report
_Source: `.omx/reviews/brutal-porting-audit/shared-report.md`_

# Brutal Porting Audit — Shared Report

This file is append-oriented.
Do not delete or overwrite another worker's section.
Each worker should add findings only inside their own section and may append dated follow-ups below prior entries.

## Worker 1 — Runtime, contracts, hidden logic, parity

_Pending findings._

### Audit update — 2026-04-06
- **Broken operator contract:** the README’s “reliable, fully-verified” fallback command currently crashes because `main.py` passes unsupported `tick_delay_seconds` / `control_file` kwargs into `SimulationConfig` (`README.md:66-72`, `main.py:87-103`, `simulation/stub.py:22-39`).
- **Synthetic peer behavior:** peer mode still hardcodes same-origin starts, one-tick teleport movement, and a forced target probe after 100s (`simulation/peer_runtime.py:73-75`, `simulation/peer_runtime.py:568-575`, `simulation/peer_runtime.py:611-613`).
- **Failure semantics are dishonest:** injected peer failure ends in `os._exit(0)`, so the launcher cannot treat dropout as a failed process (`simulation/peer_runtime.py:540-546`, `scripts/run_local_peers.py:93-111`).
- **Parity overclaim risk:** multi-process “BFT” is still coordinator-centralized, proof logs are partly synthesized for the demo, Vertex fails open to stub delivery, and the ROS lane remains a bring-up surface rather than a parity-grade port (`simulation/peer_runtime.py:468-485`, `simulation/peer_runtime.py:492-537`, `scripts/run_local_peers.py:121-188`, `core/mesh.py:215-239`, `docs/ros2-live-validation.md:88-94`).
- **Worker-1 bottom line:** current runnable behavior is real enough to demo, but the repo is still carrying major parity theater in runtime contracts, proof artifacts, and port-target framing.

## Worker 2 — Frontend, TUI, operator experience, UX debt

_Pending findings._

### 2026-04-06 — Worker 2 summary

- **Evidence:** `entropy_hunt_v2.html:353-376` still centers the operator console on `synthetic demo` while keeping replay/live actions mixed with demo-only actions like `drop packets 20%`, `auto demo`, `kill drone`, and `revive all`.
- **Inference:** The primary browser console is still a scripted demo surface first and a trustworthy operator surface second.

- **Evidence:** `entropy_hunt_v2.html:751-769` exits replay/live mode by reloading the entire page.
- **Inference:** State management is not coherent; the UX falls back to browser reset instead of supporting a clean in-app transition.

- **Evidence:** `frontend/index.template.html:16-18`, `41-48`, and `76-90` market the packaged shell as deployable and live-snapshot-capable, while the live path still depends on localhost helpers and copied standalone HTML consoles.
- **Inference:** The packaged shell currently behaves more like a demo brochure than a production-real operator interface.

- **Evidence:** `dashboard/tui_monitor_scene.ts:198-216` creates a `detailBox`, but `dashboard/tui_monitor_layout.ts:125-129` permanently hides it.
- **Inference:** The OpenTUI monitor already contains dead UI branches and is accruing architecture debt faster than operator value.

- **Evidence:** `entropy_hunt_v2.html:1-19` uses a light palette, while `dashboard/tui_theme.ts:22-40` claims parity with that HTML surface but defines a dark-shell palette instead.
- **Inference:** Cross-surface frontend parity is being described more strongly than it is actually delivered.

- **Evidence:** `README.md:3-10` and `README.md:153-156` describe multiple concurrent operator surfaces: packaged shell, two static browser consoles, OpenTUI monitor, plus Python fallback.
- **Inference:** Frontend drift is structurally built in; the port needs consolidation, not more surfaces.

- **Evidence:** `package.json:5-15,29-30` is Bun-first, but `docs/frontend-qa-checklist.md:5-8`, `docs/vercel-deploy.md:11-15`, `19-27`, `31-46`, and `frontend/index.template.html:44-48` still instruct users to run `npm`.
- **Inference:** Even the operator/deploy story is internally inconsistent, which weakens confidence before deeper runtime issues are considered.

- **Evidence:** `entropy_hunt_v2.html:474-482`, `526-539`, and `648-660` hard-code five drones and a fixed grid shape; `entropy_hunt_mockup.html:275-289` and `368-375` do the same for a `10x10` replay-only mockup, despite `README.md:60-64` advertising custom run shapes.
- **Inference:** The browser UIs are tuned to one canned scenario, not to the broader runtime contract the repo claims to expose.

- **Evidence:** `dashboard/tui_theme.ts` fixes `gridSize = 10`, `maxEvents = 12`, `maxDronesVisible = 5`, and `dashboard/tui_monitor_model.ts:155-178` clamps/slices incoming grid, drone, and event data to those limits.
- **Inference:** The OpenTUI monitor also silently compresses larger runs back into demo-scale assumptions rather than honestly representing them.

- **Evidence:** `entropy_hunt_mockup.html:291-311` and `423-470` maintain an entire independent synthetic simulation path, and `scripts/build_frontend.py:112-113` still ships that file as a first-class packaged surface.
- **Inference:** The minimal mockup is not just a fallback view; it is another parity-drift vector that should probably be deleted or radically demoted.

- **Evidence:** `dashboard/tui_monitor_input.ts:27-39` and `73-132` hide most TUI controls behind undocumented keyboard chords and punctuation shortcuts.
- **Inference:** The terminal monitor currently behaves like an insider tool, not an operator-friendly interface with clear discoverability.

- **Evidence:** `entropy_hunt_v2.html:658-666` resets imported cell owners to `-1`, `entropy_hunt_mockup.html:377-378` resets the full claimed matrix, and both browser consoles map replay drones by array index instead of durable identity (`entropy_hunt_v2.html:684-698`, `entropy_hunt_mockup.html:380-397`).
- **Inference:** The browser UIs are discarding and mutating real coordination state during import, so they cannot be trusted as faithful parity viewers.

- **Evidence:** `dashboard/tui_monitor.py:46-79` hard-codes `mesh_mode = "real"` and reduces state for the Python fallback, while `dashboard/tui.py:75-127` renders a much older coarse terminal frame.
- **Inference:** The Python fallback is not a parity-preserving backup monitor; it is another downgraded frontend branch that broadens drift.

- **Evidence:** the runtime transport contract carries `claimed_cell` (`simulation/peer_protocol.py:157-179`, `simulation/peer_runtime.py:309-320`), but both peer/stub summary payloads drop it (`simulation/peer_runtime.py:731-742`, `simulation/stub.py:708-718`), and `core/certainty_map.py:177-192` exports certainty rows without ownership fields.
- **Inference:** Ownership/claim-state loss is upstream in the snapshot/export contract, not just a frontend rendering bug.

- **Evidence:** the browser consoles then wipe any remaining claim semantics on import (`entropy_hunt_v2.html:658-666`, `entropy_hunt_mockup.html:377-378`) while still keeping local claim logic around (`entropy_hunt_v2.html:595-603`).
- **Inference:** The HTML operator surfaces actively mutate coordination state toward demo cleanliness instead of preserving runtime truth.

- **Evidence:** runtime payloads carry durable drone ids and often sort by id (`scripts/serve_live_runtime.py:64`, `simulation/peer_runtime.py:731-742`), but browser consoles remap drones by array index (`entropy_hunt_v2.html:684-698`, `entropy_hunt_mockup.html:380-397`).
- **Inference:** Identity/order coupling is a real parity risk: one ordering shift can misattribute behavior to the wrong drone.

- **Evidence:** the Python fallback hard-codes `mesh_mode = "real"` (`dashboard/tui_monitor.py:50`), truncates state (`dashboard/tui_monitor.py:64-79`), and lacks the richer control/source/staleness model present in `dashboard/tui_monitor_model.ts:31-54`.
- **Inference:** The fallback is materially less truthful, not just visually simpler.

## Worker 3 — Tests, performance, throughput, load-time, LOC reduction

### 2026-04-06 summary
- **Scorecard:** current runnable behavior `4/10`; explicit documented promises `2/10`; intended port target `1/10`.
- **Hard evidence:** deploy/docs/test contract is internally inconsistent (`README.md:127-131`, `package.json:13-14`, `vercel.json:2-4`, `tests/test_deployment_config.py:7-20`, `docs/vercel-deploy.md:11-15`, `docs/frontend-qa-checklist.md:5-8`).
- **Hard evidence:** default Bun-first path appears wall-clock throttled because `runtime/config.ts:45-65` enables the monitor by default, `runtime/run.ts:112-128` maps missing tick delay to `tickSeconds`, and `simulation/peer_runtime.py:688-699` sleeps every tick.
- **Hard evidence:** documented stress envelope is weak on larger grids (`submission/14_stress_test_summary.md:17-23`) and there is no in-repo perf/load tooling.
- **Hard evidence:** the Bun/runtime wrapper surface is largely untested; existing tests mostly cover source HTML behavior and a narrow subset of Python runtime behavior.
- **Simplification:** dedupe the two HTML consoles, delete or relocate `demo.typescript`, and stop carrying generated build/session/run artifacts in the main tree.
- Full detail: `worker-3.md`


## Leader synthesis

### 2026-04-06 synthesis

#### Overall verdict
- **Current runnable behavior:** demo-capable, but not parity-capable.
- **Documented promises:** materially overstated in multiple places.
- **Intended port target:** still far from complete.

#### Brutal bottom line
- This repo can stage a convincing demo, but it is still carrying a lot of **parity theater**.
- The sharpest pattern is not “nothing works”; it is **selective honesty**:
  - deeper docs admit caveats,
  - top-level framing still sounds stronger than the code deserves,
  - several user-facing paths are synthetic, shallowly verified, or outright broken.

#### Highest-severity findings
1. **Broken operator contract:** the advertised fallback/stub CLI currently crashes because `main.py` passes unsupported fields into `SimulationConfig`.
2. **Centralized “BFT”:** the multi-process runtime is still coordinator-driven, not parity-grade peer BFT.
3. **Synthetic runtime shortcuts:** same-origin starts, teleport movement, and forced target probing are still shaping demo behavior.
4. **Dishonest failure semantics:** injected failure exits with code `0`, so supervisors can treat failure as success.
5. **Curated evidence artifacts:** `proofs.jsonl` is partly synthesized post-run instead of being a raw operational ledger.
6. **Weak readiness signaling:** the Bun launcher declares readiness after one snapshot file and one successful HTTP read.
7. **Frontend fragmentation:** too many operator surfaces exist without one shared presenter/state contract.
8. **Demo-scale UI assumptions:** browser and TUI surfaces clamp or reject larger-than-demo configurations.
9. **Verification story is incoherent:** docs, tests, deploy config, and scripts disagree on the real build/deploy/verification contract.
10. **Port lanes are still scaffolds:** ROS / Vertex / Webots remain bring-up or adapter surfaces, not parity-grade runtime ports.

#### What is actually solid
- There is real implementation value here:
  - the peer lane runs,
  - focused UI/TUI tests exist,
  - the monitor/build surfaces compile,
  - some docs are candid about what remains synthetic.
- The problem is **trustworthiness and consolidation**, not total absence of engineering.

#### Main parity gaps still visible
- no trustworthy fallback CLI path
- no honest distributed-BFT parity in multi-process mode
- no raw proof/evidence pipeline
- no single deployable operator surface that is also truly live-ready
- no adaptive UI/TUI story for larger runs
- no strong automated guardrails for launcher behavior, readiness, packaging, and perf

#### Hidden logic risks
- demo success depends on silent convergence shortcuts
- failure can be masked as success at orchestration level
- readiness can be overstated before the swarm is actually healthy
- packaging/build outputs can drift away from tested source behavior
- frontend parity language is stronger than frontend parity reality

#### Most credible 20% reduction opportunities
- remove or demote one HTML console, especially the mockup path
- extract shared browser logic instead of duplicating replay/entropy behavior
- stop shipping raw copied standalone surfaces as if they are one unified product
- delete/relocate generated artifacts and transcript bulk from the main repo surface
- collapse onto one deploy toolchain and one operator story
- cut dead or permanently hidden UI branches in the TUI

#### Recommended next actions
1. Fix the broken fallback CLI before claiming any “fully verified” operator path.
2. Rewrite top-level README/runtime framing to match actual maturity.
3. Collapse the operator surface count instead of extending it.
4. Separate synthetic-demo controls from live/replay monitoring completely.
5. Add real launcher/readiness/packaged-output regression coverage.
6. Treat ROS/Vertex/Webots as explicit experimental lanes until parity evidence exists.

#### Status
- Worker 1 findings incorporated.
- Worker 2 direct mailbox summary received and incorporated.
- Worker 3 findings incorporated.

### Audit follow-up — 2026-04-06
- **Weak readiness contract:** the Bun launcher declares the runtime `ready` after one snapshot file and one successful HTTP read, not after all requested peers or core coordination behavior are actually live (`runtime/health.ts:4-18,40-42`; `runtime/run.ts:441-457`).
- **Demo-success bias in orchestration:** session completion still hinges on process exit codes, while injected peer failure deliberately exits `0`, so runtime summaries can report clean completion across known failure events (`simulation/peer_runtime.py:540-546`; `runtime/processes.ts:100-115`; `runtime/run.ts:497-500`).
- **ROS lane still looks thin:** ROS defaults to a 2-drone launch and remains an observer/bring-up lane over simplified node behavior rather than a parity-grade port of the five-peer runtime story (`launch/demo.launch.py:53-67`; `operator_node.py:33-62,135-185`; `docs/ros2-topic-contract.md:29-32`).

### 2026-04-06 follow-up
- **Live polling risk:** `scripts/serve_live_runtime.py:24-31,34-115,137-150` rereads and re-merges all peer JSON on every GET, while browser/TUI clients poll at `1000ms` and `400ms` intervals (`entropy_hunt_v2.html:726-748`, `dashboard/tui_theme.ts:134-140`). Observability cost scales badly with run size.
- **Readiness overclaim:** `runtime/health.ts:4-18,40-42` marks the runtime ready after one snapshot file and one HTTP success, not after the requested swarm is actually present.
- **Build step is shallow:** `scripts/build_frontend.py:100-126` mostly copies source HTML into `dist/`; `tests/test_frontend_build.py:8-21` only checks existence plus one string.


## Worker 1
_Source: `.omx/reviews/brutal-porting-audit/worker-1.md`_

# Worker 1 Report — Runtime / Contracts / Hidden Logic / Parity

Focus:
- runtime behavior and orchestration paths
- contract mismatches
- hidden logic issues
- present behavior vs documented behavior
- synthetic or misleading “done” claims

Rules:
- append findings; do not rewrite history
- mark each finding as Evidence or Inference
- call out parity gaps brutally


## Audit pass — 2026-04-06

### Scorecard against the three baselines

| Baseline | Score | Verdict |
| --- | --- | --- |
| Current runnable behavior | 2/5 | Peer mode runs, but the advertised stub/fallback operator path is currently broken and several “runtime” behaviors are synthetic shortcuts. |
| Explicit documented promises | 2/5 | README admits some debt, but it still overstates verification, BFT completeness, and the “rawness” of proof artifacts. |
| Intended port target | 1/5 | ROS/Webots/Vertex remain bring-up surfaces or adapters, not parity-grade runtime ports. |

### Finding 1 — the README’s “reliable, fully-verified” fallback path is not runnable

**Evidence**
- README calls the single-process fallback the “reliable, fully-verified path” and gives `python3 main.py ...` as the operator command (`README.md:66-72`).
- `main.py` passes `tick_delay_seconds` and `control_file` into `SimulationConfig` (`main.py:87-103`).
- `SimulationConfig` does not define either field (`simulation/stub.py:22-39`).
- Running the documented command in `/home/kpa/entropyhunt` on April 6, 2026 failed immediately with `TypeError: SimulationConfig.__init__() got an unexpected keyword argument 'tick_delay_seconds'`.
- At the same time, `pytest -q tests/test_simulation.py` still passed (`6 passed`), proving the verification surface does not cover the shipping CLI entrypoint.

**Inference**
- The repo currently tests the simulation object, not the documented operator contract.
- The most prominently defended fallback path is a broken parity claim right now.

### Finding 2 — the peer runtime is still materially synthetic in ways the README soft-pedals

**Evidence**
- Every peer starts at `(0, 0)` regardless of peer identity or grid size (`simulation/peer_runtime.py:73-75`).
- After a claim resolves, a drone teleports straight to the target cell in one tick (`simulation/peer_runtime.py:602-613`).
- After 100 seconds, the runtime can bypass normal selection and fabricate a `ZoneSelectionProxy` that directly targets the survivor coordinate (`simulation/peer_runtime.py:40-42,568-575`).

**Inference**
- The multi-process lane is not just “rough around the edges”; core search/motion behavior is still being staged so the demo converges.
- Any parity narrative that treats peer mode as a realistic spatial runtime is overstated.

### Finding 3 — peer-mode failure handling is disguised as success

**Evidence**
- When a peer “fails,” the runtime logs the failure, writes a map, closes the mesh, and then calls `os._exit(0)` (`simulation/peer_runtime.py:540-546`).
- The launcher computes overall status from child process exit codes (`scripts/run_local_peers.py:93-111`).
- Because the failed peer exits with code 0, the orchestrator cannot distinguish injected dropout from clean success via exit status alone.

**Inference**
- This is demo-friendly but operationally dishonest: the process advertises a failure event while returning success semantics to its supervisor.
- Anything upstream that relies on exit codes will under-report failure severity.

### Finding 4 — multi-process “BFT” is still centralized coordinator logic, not peer-parity BFT

**Evidence**
- README explicitly says the local UDP peer runtime still uses coordinator-confirmed result finalization and is not Byzantine-fault-tolerant (`README.md:153-156,218-219`).
- The runtime elects a coordinator as the minimum known peer id (`simulation/peer_runtime.py:277-281`).
- Only the coordinator resolves pending claims and stale releases (`simulation/peer_runtime.py:468-485,492-537`).
- The stub path has actual mesh vote collection logic in `core/bft.py`, but the peer path does not reuse that distributed vote loop.

**Inference**
- The gap is not merely “transport missing”; the separate-process runtime is still architecturally centralized.
- Saying “coordination logic is complete; transport is the gap” is too generous for the peer lane.

### Finding 5 — the peer proof log is partly synthesized for the shipping demo

**Evidence**
- README says the local peer demo “appends proofs under the same runtime session” (`README.md:96-103`).
- `scripts/run_local_peers.py` explicitly “Collapse[s] peer outputs into one evidence file for the shipping demo” (`scripts/run_local_peers.py:121-123`).
- That routine re-reads outputs, manufactures `auction` events from `bft_result`, merges selected event types from snapshots, de-duplicates, sorts, and rewrites the proofs file (`scripts/run_local_peers.py:121-188`).
- In the runtime itself, `_append_proof` only appends BFT result payloads; it is not a complete raw event stream (`simulation/peer_runtime.py:233-262`).

**Inference**
- `proofs.jsonl` is a curated artifact, not a faithful live append-only ledger of everything the peer runtime did.
- The documentation makes the artifact sound more direct/raw than it actually is.

### Finding 6 — the “real transport” and port-target lanes remain adapter surfaces that fail open

**Evidence**
- README says Vertex is still synthetic/not-yet-live and the adapter requires a matching shared-library build (`README.md:182-184`).
- `VertexMeshBus` silently falls back to the in-process bus if the helper is missing, exits early, or rejects publish (`core/mesh.py:215-239,257-273`).
- README presents ROS 2 commands in the runtime matrix (`README.md:30-36`), but the ROS topic contract itself is labeled “planned” and says no ROS 2 claim should be made until backed by real nodes (`docs/ros2-topic-contract.md:1-3,29-32`).
- The ROS validation doc explicitly says even a passing validation script does **not** prove parity with the UDP runtime or mature consensus over ROS (`docs/ros2-live-validation.md:88-94`).
- The ROS operator server can be read-only and return `405` for control attempts (`ros2_ws/src/entropy_hunt_ros2/entropy_hunt_ros2/operator_server.py:46-53`).
- The ROS drone node uses simplified winner=min(contender), fallback `x+1`, linear certainty growth, and threshold-triggered survivor publication (`ros2_ws/src/entropy_hunt_ros2/entropy_hunt_ros2/drone_node.py:71-99,134-195`).

**Inference**
- The intended port target is not close to parity yet; it is still a collection of bring-up adapters and simplified placeholder behaviors.
- The repo is relatively honest in the ROS docs, but the top-level runtime matrix still risks being read as stronger delivery than the code deserves.

### Finding 7 — documentation caveats are unevenly distributed, which creates parity-lie risk

**Evidence**
- The frontend docs are cautious: they explicitly call out synthetic demo mode and warn not to imply live Vertex/FoxMQ integration (`docs/frontend-qa-checklist.md:17-21,36`; `docs/vercel-deploy.md:49`).
- The README uses broader framing such as “ships several aligned prototype surfaces” and “standard-library-only” while simultaneously exposing Bun/OpenTUI dependencies and optional transport/runtime lanes (`README.md:3-12`; `package.json:32-44`; `requirements.txt:1-6`; `core/mesh.py:367-373`).

**Inference**
- The detailed docs are more honest than the landing narrative.
- The main parity-lie risk is not hidden code alone; it is the mismatch between README framing and the more caveated lower-level docs.

### High-priority missing parity list
- The advertised stub/fallback CLI is broken at startup.
- Multi-process runtime still centralizes claim resolution.
- Motion/search behavior is heavily staged (same spawn point, teleport movement, forced target probe).
- Failure injection exits successfully instead of surfacing an error to orchestration.
- Proof artifacts are partially synthesized after the run.
- ROS lane is still a bring-up surface, not a parity-grade port.
- Vertex “real” transport fails open back to stub behavior.

### Hidden-logic risks
- Demo success currently depends on invisible convergence shortcuts rather than only on declared coordination logic.
- Supervisors can mistake injected failure for success because the failing peer returns exit code 0.
- Reviewers can mistake curated proofs for raw operational evidence.
- README wording can cause downstream readers to over-credit maturity relative to what the code actually guarantees.

### ~20% LOC reduction opportunities without losing real capability
- Delete or quarantine dead-end parity theater from top-level operator claims instead of adding more glue: the broken stub CLI wiring, the fail-open Vertex path, and the partially synthetic ROS/operator control lane are all candidates for demotion behind explicit feature flags/docs.
- Separate “shipping demo artifact generation” from runtime execution: `scripts/run_local_peers.py` currently mixes orchestration with proof synthesis and could be simplified by making the synthesis step explicit.
- Collapse duplicated story surfaces around runtime maturity so README, runtime matrix, and caveat docs stop contradicting one another.


## Follow-up audit pass — 2026-04-06 (read-only continuation)

### Finding 8 — launcher readiness is a weak liveness check dressed up as runtime readiness

**Evidence**
- `waitForRuntimeReady()` only waits for **one** JSON snapshot file plus one successful HTTP response (`runtime/health.ts:40-42`).
- `waitForSnapshots()` considers the backend ready as soon as the snapshot directory contains at least one `.json` file (`runtime/health.ts:4-18`).
- The launcher then marks the whole session `ready` and may attach the monitor immediately (`runtime/run.ts:441-457`).
- This check is independent of requested peer count, BFT activity, dropout handling, or snapshot schema completeness.

**Inference**
- The Bun launcher’s “backend ready” state is weaker than it sounds; it really means “some snapshot endpoint answered once.”
- For multi-peer demos, this can overstate runtime health and parity before the system has actually converged or even fully come online.

### Finding 9 — the runtime shell still conflates demo liveness with operational correctness

**Evidence**
- The session summary and manifest promote `status=completed` whenever the launcher exits with code 0 (`runtime/run.ts:497-500`).
- Peer failure injection intentionally exits with code 0 (`simulation/peer_runtime.py:540-546`).
- `spawnManagedProcess()` and `waitForExit()` preserve that success code and do not reinterpret failure events from logs or snapshots (`runtime/processes.ts:100-115`).

**Inference**
- The top-level runtime shell is structurally biased toward reporting demo success, not operational truth.
- A run can contain a first-class failure event and still be treated as a cleanly completed session end-to-end.

### Finding 10 — ROS launch defaults and runtime framing still read like a thin bring-up lane, not a parity port

**Evidence**
- The ROS launch file defaults to only `count=2` drones (`ros2_ws/src/entropy_hunt_ros2/launch/demo.launch.py:53-67`), while the main README narrative and peer baseline center on five-drone behavior (`README.md:153-156,176-180`).
- The ROS operator node publishes a snapshot built from topic observations and exposes runtime control metadata, but it is fundamentally an observer/aggregator over simplified drone-node behavior (`operator_node.py:33-62,135-185`; `drone_node.py:71-99,134-195`).
- The ROS topic contract itself still labels the lane as planned and explicitly says no ROS 2 claim should be made until backed by real nodes and launch execution (`docs/ros2-topic-contract.md:1-3,29-32`).

**Inference**
- The ROS lane is still closer to a supervised demo scaffold than a parity-preserving port of the current peer runtime.
- Even where code exists, the default scale and behavior undercut the impression of a serious migration lane.


## Worker 2
_Source: `.omx/reviews/brutal-porting-audit/worker-2.md`_

# Worker 2 Report — Frontend / TUI / Operator Experience

Focus:
- dashboard and monitor quality
- UX, operator flow, layout, discoverability
- frontend maintainability and architectural debt
- visual or interaction parity gaps
- places where the frontend is bad, fragile, misleading, or unfinished

Rules:
- append findings; do not rewrite history
- mark each finding as Evidence or Inference
- be explicit about user-visible pain

## Audit update — 2026-04-06 UTC

### Three-baseline scorecard

| Baseline | Score | Verdict |
| --- | --- | --- |
| Current runnable behavior | 5/10 | The HTML consoles, packaged shell, and OpenTUI monitor all build/test, but the operator experience is still demo-first and fragile. |
| Explicit documented promises | 3/10 | README sells a Bun-first operator path and deployable shell, but the shipped surfaces still depend on localhost helpers and contradict their own tooling story. |
| Intended port target | 2/10 | This is not converging on one trustworthy operator-facing product; it is splintering into multiple partially-overlapping fronts. |

### Finding 1 — The “rich console” is still a demo console wearing ops-console clothing

**Evidence**
- `entropy_hunt_v2.html:353-376` defaults the mode chip to `synthetic demo` and keeps `load replay`, `connect live`, `drop packets 20%`, `auto demo off`, `kill drone`, and `revive all` in the same top bar.
- `entropy_hunt_v2.html:516-523` only disables replay/live buttons on source-mode changes; the demo/destructive buttons stay available.
- `entropy_hunt_v2.html:1396-1398` stops the synthetic tick loop in replay/live mode, which means the surface is explicitly bifurcated between “real-ish data viewer” and “local scripted demo”.
- `docs/frontend-qa-checklist.md:16-21` treats “default load shows synthetic demo mode” as the happy-path expectation.

**Inference**
- This is misleading operator UX. The surface asks the user to trust live/replay state while still foregrounding synthetic chaos controls that are not clearly segregated from live monitoring.
- In a real handoff, the first question will be “what is actually live right now?” and this UI does not answer it cleanly.

### Finding 2 — Leaving replay/live mode is a hard reload, not a real interaction flow

**Evidence**
- `entropy_hunt_v2.html:751-769` implements both `disconnectLive()` and `clearReplay()` with `window.location.reload()`.
- `docs/frontend-qa-checklist.md:21` explicitly normalizes that behavior: “Clear replay restores or reloads back to synthetic mode.”

**Inference**
- The console does not own a coherent state model. It punts reset logic to a full browser reload.
- That is bad operator ergonomics: context disappears, errors vanish, and side-by-side comparison between replay/live/synthetic states becomes clumsy.

### Finding 3 — The packaged shell oversells live usefulness

**Evidence**
- `frontend/index.template.html:16-18` calls the shell “one deployable static site”.
- `frontend/index.template.html:22-24` elevates `Open rich console` as a primary CTA.
- `frontend/index.template.html:41-48` labels the artifact area as `replay or live snapshot path` and even prints run commands inline.
- `frontend/index.template.html:76-90` says the rich console is “live-snapshot-capable” while also admitting the packaged shell is static and live data still requires local helpers.
- `scripts/build_frontend.py:111-116` just copies `entropy_hunt_v2.html` and `entropy_hunt_mockup.html` into `dist/`; there is no packaging-time adaptation that makes the deployed console more production-real.
- `README.md:133-140` says the rich console can connect to `http://127.0.0.1:8765/snapshot.json`, i.e. localhost helper infrastructure.

**Inference**
- The deployed artifact is closer to a demo brochure than a serious ops surface.
- “Deployable” currently means “can host static files”, not “can actually operate the port in a believable way”.

### Finding 4 — The TUI is over-fragmented and already contains dead UI branches

**Evidence**
- The `dashboard/` folder currently contains 29 top-level files, including multiple monitor-specific modules plus dedicated tests and support files.
- `dashboard/tui_monitor_scene.ts:198-216` constructs a `detailBox` with child renderables.
- `dashboard/tui_monitor_layout.ts:125-129` then permanently forces that same `detailBox` to `visible = false`, `height = 0`, `flexGrow = 0`.
- `dashboard/tui_monitor_input.ts:27-39` defines multiple hidden keyboard mode/focus shortcuts (`1..5`, `o/d/m/c/g`, `h/r/e`).
- `dashboard/tui_monitor_input.ts:73-132` adds a second layer of config controls with arrow keys plus `[`, `]`, `-`, `_`, `+`, `=`.

**Inference**
- This is already too much UI surface for the amount of operator value being delivered.
- The TUI is becoming a mode-heavy control puzzle with dead code left behind, which is a maintainability smell and a discoverability problem.

### Finding 5 — Visual parity claims are weak enough to be misleading

**Evidence**
- `entropy_hunt_v2.html:1-19` defines a light UI palette (`#ffffff`, `#f3f4f6`, etc.).
- `dashboard/tui_theme.ts:22-29` claims the OpenTUI theme is “derived from entropy_hunt_v2.html” and is meant to let the monitor “reach parity”.
- `dashboard/tui_theme.ts:32-40` immediately defines a dark-shell palette (`#0f172a`, `#0b1220`, etc.) that does not match the HTML console’s palette.

**Inference**
- “Parity” currently means “parallel reinterpretation”, not “same operator experience across surfaces”.
- The port has not stabilized visually; it has forked aesthetically.

### Finding 6 — There are too many operator surfaces and no shared source of truth

**Evidence**
- `README.md:3-10` lists a packaged shell plus two static operator consoles.
- `README.md:153-156` says the OpenTUI monitor is separate and primary for live peer snapshots.
- `README.md:168-169` still keeps `dashboard/tui_monitor.py` as a Python fallback.
- `scripts/build_frontend.py:111-116` copies raw standalone HTML consoles into the packaged shell instead of building those surfaces from a shared presenter/state layer.

**Inference**
- Frontend parity drift is structurally guaranteed. Any real UX fix must now be considered across at least: rich HTML console, minimal HTML mockup, OpenTUI monitor, and Python fallback.
- This is exactly the wrong direction for a brownfield port that should be consolidating.

### Finding 7 — Even the basic tooling story is internally inconsistent

**Evidence**
- `package.json:5-15,29-30` positions the project as Bun-first (`bun run build`, `bun run hunt`, `bun run hunt:serve`).
- `docs/frontend-qa-checklist.md:5-8` still tells reviewers to run `npm run build` and `npm run preview`.
- `docs/vercel-deploy.md:11-15`, `19-27`, and `31-46` continue to document `npm run build`, `npm run deploy:preview`, and `npm run deploy:prod`.
- `frontend/index.template.html:44-48` repeats `npm run build`, `npm run preview`, `npm run live:peers`, and `npm run live:serve` inside the deployed site itself.

**Inference**
- The first-run story is sloppy. A user following the docs and a user following the README are being told two different truths.
- This is exactly the kind of small but corrosive mismatch that makes the whole port feel less trustworthy than it really is.

### What is actually working today

**Evidence**
- `bun test dashboard/tui_monitor_logic.test.ts dashboard/tui_monitor_frame.test.ts dashboard/tui_opentui_interaction.test.ts` → 25/25 passing on 2026-04-06.
- `node --test entropy_hunt_ui.test.mjs` → 9/9 passing on 2026-04-06.
- `bun run build && bun run build:monitor` → succeeded on 2026-04-06; `build/entropyhunt-monitor` compiled successfully.

**Inference**
- There is a real quality floor here. The problem is not “nothing works”.
- The problem is that passing tests are proving fixture parity and scripted flows, not that the operator-facing product has converged into one honest, low-confusion surface.

### Missing parity / operator failures

- No single surface is both deployable and meaningfully live-ready.
- Live/replay states are not cleanly separated from synthetic/demo controls.
- Replay/live exit behavior still depends on a full page reload.
- HTML console, minimal mockup, OpenTUI monitor, and Python fallback do not share one presentation model.
- Visual parity language is stronger than the actual parity delivered.

### Simplification opportunities (~20% LOC reduction without losing capability)

- Retire one HTML console (`entropy_hunt_mockup.html` is the most obvious candidate) and stop carrying two browser surfaces with overlapping purpose.
- Delete the dead `detailBox` branch in the OpenTUI path or make it real; keeping a permanently hidden panel is pure waste.
- Move demo-only actions behind an explicit synthetic/demo mode instead of leaving them in the same command band as replay/live actions.
- Stop copying standalone consoles into `dist/` as-is; build one shared operator surface with one shared state/presenter path.
- Collapse the operator story to one primary live monitor and one static artifact viewer. The current four-surface story is too much.

## Follow-up findings — 2026-04-06 UTC

### Finding 8 — The browser consoles are hard-coded to one grid and one swarm shape

**Evidence**
- `README.md:60-64` explicitly advertises custom runtime flags like `--count 8 --duration 240 --output-dir peer-runs-custom`.
- `entropy_hunt_v2.html:474-482` hard-codes five start positions, five colors, and five drone names.
- `entropy_hunt_v2.html:526-539` constructs a fixed `GRID_SIZE`-based grid in-browser.
- `entropy_hunt_v2.html:648-660` rejects any replay/live payload whose row count or column count differs from that fixed `GRID_SIZE`.
- `entropy_hunt_mockup.html:275-289` hard-codes `G = 10` plus five drone names/colors.
- `entropy_hunt_mockup.html:368-375` rejects any replay payload that is not exactly `10x10`.

**Inference**
- The HTML operator surfaces are not generic views over runtime state; they are demos tuned to one canonical happy-path shape.
- That is a direct parity hole against the repo’s own “custom flags” story. The frontend cannot honestly claim to support the broader runtime envelope if it crashes or refuses payloads outside one canned geometry.

### Finding 9 — The OpenTUI path also truncates scale instead of representing it

**Evidence**
- `dashboard/tui_monitor_model.ts:73-76` fixes `MAX_GRID_DIMENSION`, `MAX_EVENT_LINES`, and `MAX_DRONE_LINES` from `TUI_LAYOUT`.
- `dashboard/tui_theme.ts` defines `TUI_LAYOUT.gridSize = 10`, `maxEvents = 12`, and `maxDronesVisible = 5`.
- `dashboard/tui_monitor_model.ts:155-156` clamps the incoming `gridSize` to `MAX_GRID_DIMENSION`.
- `dashboard/tui_monitor_model.ts:159-178` slices drones to `MAX_DRONE_LINES`.
- `dashboard/tui_monitor_model.ts:180-187` slices events to `MAX_EVENT_LINES`.

**Inference**
- The terminal monitor is not an adaptive operator surface either; it is a capped dashboard that silently compresses larger runs back into the demo-scale worldview.
- This is especially bad because the README markets stress presets and larger custom runs. An operator can launch a larger run while the frontend quietly hides part of it.

### Finding 10 — The “minimal mockup” is not a fallback; it is another synthetic fork

**Evidence**
- `entropy_hunt_mockup.html:217-223` defaults to `synthetic demo`, only exposes replay load/reset, and has no live-connect path at all.
- `entropy_hunt_mockup.html:291-311` initializes its own synthetic grid, claim map, drones, counters, and replay state.
- `entropy_hunt_mockup.html:423-470` contains its own assignment/auction/search simulation logic instead of consuming a shared state presenter.
- `scripts/build_frontend.py:112-113` ships this mockup into `dist/` beside the rich console as a first-class artifact.

**Inference**
- This file is not a thin view layer or reference shell. It is another independently-maintained simulation surface.
- Keeping it around increases audit surface, parity drift, and documentation burden for very little operator benefit.

### Finding 11 — The TUI control contract is hidden, overloaded, and non-obvious

**Evidence**
- `dashboard/tui_monitor_input.ts:27-39` defines five display-mode shortcuts and three focus shortcuts.
- `dashboard/tui_monitor_input.ts:73-132` overloads config editing onto arrow keys and punctuation keys.
- `dashboard/tui_monitor_io.ts:15-32` exposes only `--source` and `--interval-ms` as explicit CLI affordances.
- The visible screen structure in the committed fixtures emphasizes status and panels, but not a clear control legend or onboarding step (`dashboard/__fixtures__/tui_monitor_wide.txt`, `dashboard/__fixtures__/tui_monitor_compact.txt`).

**Inference**
- The TUI is learnable only if you already know the hidden key map or read source/tests.
- That is bad operator experience debt: power-user controls are fine, but buried controls without discoverability turn the monitor into an insider tool rather than a transferable interface.

### Finding 12 — The browser consoles actively discard coordination-state parity

**Evidence**
- `entropy_hunt_v2.html:658-666` loads replay/live cell certainty but forcibly resets every cell owner to `-1`.
- `entropy_hunt_mockup.html:377-378` rebuilds replay state while resetting the whole `claimed` matrix to `-1`.
- `entropy_hunt_v2.html:684-698` maps replay drones strictly by array index.
- `entropy_hunt_mockup.html:380-397` also maps replay drones strictly by array index and then rewrites ids to local demo names (`d_1`…`d_5`).

**Inference**
- These UIs are not just incomplete — they are falsifying state. Ownership/claim information is thrown away during import, so the operator cannot actually inspect coordination parity from replay/live payloads.
- Index-based drone mapping is another silent parity bug: if order changes, the UI can display the wrong drone as the wrong actor without any visible warning.

### Finding 13 — The Python fallback monitor is a visibly downgraded, partly synthetic surface

**Evidence**
- `dashboard/tui_monitor.py:46-79` constructs a simplified monitor state with `mesh_mode = "real"` hard-coded, only the last 8 events, and a reduced drone summary.
- `dashboard/tui.py:75-127` renders a much older one-line-header / one-line-drone-strip terminal frame, not the richer OpenTUI interaction model.
- `README.md:168-169` still presents this Python fallback alongside the newer OpenTUI path.

**Inference**
- The fallback is not a parity-preserving backup. It is a separate, degraded representation that can misstate mesh state and hide operator context.
- Keeping this path active in the product story makes the frontend surface area broader and less trustworthy.

### Finding 14 — Claim/ownership-state loss starts in the export contract, not just in the UI

**Evidence**
- `simulation/peer_runtime.py:309-320` publishes per-drone runtime state with `claimed_cell`.
- `simulation/peer_protocol.py:157-179` defines `claimed_cell` as part of the drone-state payload contract.
- `simulation/peer_runtime.py:731-742` drops `claimed_cell` from the summary drones written into final/live payloads.
- `simulation/stub.py:708-718` also writes drone summaries without `claimed_cell`.
- `core/certainty_map.py:177-192` serializes grid rows with certainty, entropy, timestamps, and `updated_by`, but no ownership field.
- `simulation/peer_runtime.py:745-761` and `simulation/stub.py:734-756` save final payloads using those ownership-free summaries and grid rows.

**Inference**
- The frontend loses claim state because the export pipeline already strips it out. By the time browser/TUI surfaces consume snapshot payloads, core coordination ownership is no longer representable.
- This is a serious parity break: the runtime has claim-state semantics, but the operator-facing artifacts are built from a contract that discards them.

### Finding 15 — The HTML consoles worsen that loss by resetting any residual claim semantics to empty

**Evidence**
- `entropy_hunt_v2.html:658-666` rewrites every imported cell owner to `-1` during replay/live import.
- `entropy_hunt_mockup.html:377-378` rebuilds the full `claimed` matrix as all `-1` during replay import.
- `entropy_hunt_v2.html:595-603` still contains in-browser claim release logic, so the rich console has a local notion of ownership even while imported ownership is wiped.

**Inference**
- Even if claim/ownership state were reintroduced into payloads, the current browser consoles would still erase it on ingest.
- This is not passive omission; it is active mutation of coordination state into a cleaner but less truthful demo representation.

### Finding 16 — Index-based drone remapping is an avoidable identity bug

**Evidence**
- `scripts/serve_live_runtime.py:64` sorts merged runtime drones by `id`.
- `simulation/peer_runtime.py:731-742` also sorts peer-runtime summary drones by `drone_id`.
- `simulation/stub.py:708-718` emits stub-mode drones in local list order, not an explicit stable identity map.
- `entropy_hunt_v2.html:684-698` binds replay drones to local UI drones by array index.
- `entropy_hunt_mockup.html:380-397` does the same and rewrites ids to local names (`d_1`…`d_5`).
- `dashboard/tui_monitor_model.ts:157-178` is safer because it preserves `drone.id`, but still slices by position in the incoming array rather than maintaining a stable keyed roster when the list exceeds visible limits.

**Inference**
- The browser surfaces are one ordering change away from lying about which drone searched, failed, or found the survivor.
- This is a classic brownfield UI bug: identity is available in the data model, but the presentation layer still treats ordering as identity.

### Finding 17 — The Python fallback degrades parity in specific, operator-visible ways

**Evidence**
- `dashboard/tui_monitor.py:50` hard-codes `mesh_mode = "real"` instead of reading the payload’s actual mesh/source state.
- `dashboard/tui_monitor.py:64-65` truncates events to the last 8.
- `dashboard/tui_monitor.py:66-79` omits source label, control URL, control capabilities, stale-data state, requested drone count, and tick timing controls that the OpenTUI model carries in `dashboard/tui_monitor_model.ts:31-54`.
- `dashboard/tui.py:122-127` renders a minimal flat event log instead of the richer focused panels and mode system.

**Inference**
- The Python fallback is not merely simpler; it is materially less truthful and less operable.
- An operator switching from OpenTUI to the fallback loses configuration/state context and may even be told the mesh is “real” when the actual source is local/stub/replay.


## Worker 3
_Source: `.omx/reviews/brutal-porting-audit/worker-3.md`_

# Worker 3 Report — Tests / Performance / Throughput / LOC Reduction

Focus:
- test coverage and missing verification
- performance, throughput, load-time, and stress-readiness
- measurement blind spots
- simplification and ~20% LOC reduction opportunities without capability loss
- areas of duplication, over-abstraction, or accidental complexity

Rules:
- append findings; do not rewrite history
- mark each finding as Evidence or Inference
- quantify performance and simplification risks where possible

## 2026-04-06 Read-only audit pass

### Three-baseline scorecard
| Baseline | Score | Reason |
| --- | --- | --- |
| Current runnable behavior | 4/10 | There is a demo lane and some focused tests, but the default Bun-first operator path is largely untested and the documented stress envelope is narrow. |
| Explicit documented promises | 2/10 | Docs, tests, and deploy scripts disagree on the build/deploy contract, so the repo's own verification story is not self-consistent. |
| Intended port target | 1/10 | Load/perf instrumentation is basically absent, the runtime envelope collapses on larger grids, and the default operator path appears wall-clock throttled. |

### Findings
1. **Evidence:** The deploy contract is internally inconsistent. `README.md:127-131` says `vercel.json` points at `bun run build`, but `vercel.json:2-4`, `docs/vercel-deploy.md:11-15`, `docs/frontend-qa-checklist.md:5-8`, and `tests/test_deployment_config.py:7-20` all expect `npm run build`; `package.json:13-14` instead uses `bun run build` for deploy scripts. This is not a subtle drift: the same repo advertises two different release contracts.
   **Evidence (earlier session on identical snapshot):** `pytest -q` failed in `tests/test_deployment_config.py::test_package_scripts_include_vercel_deploy_commands` because `package.json` says `bun run build` while the test expects `npm run build`.
   **Inference:** Release confidence is artificially inflated because the repository cannot currently agree on the command that defines a successful deploy.

2. **Evidence:** The published verification recipe is not trustworthy as written. `README.md:142-149` and `docs/vercel-deploy.md:36-43` both tell operators to run `mypy .`.
   **Evidence (earlier session on identical snapshot):** `mypy .` failed because generated ROS build output under `ros2_ws/build/.../entropy_hunt_interfaces` creates duplicate Python modules.
   **Inference:** The repo is counting generated build output as part of verification scope without maintaining that scope, which creates false confidence for anyone following the documented release path.

3. **Evidence:** The default user-facing runtime path is likely throttled by UI presence. `README.md:14-26` calls `bun run hunt` the simplest/default path. `runtime/config.ts:45-65` defaults `monitor: true` and `tickSeconds: 1`. `runtime/run.ts:112-128` turns an unspecified `tickDelaySeconds` into `tickSeconds` when the monitor is enabled. `simulation/peer_runtime.py:688-699` sleeps `self._tick_delay_seconds` every tick.
   **Inference:** The default Bun path appears to force roughly one second of wall-clock sleep per simulated tick (≈180s for the 180-tick demo, ≈240s for the 240-tick stress presets), even though the direct script path falls back to `0.1` seconds in `scripts/run_local_peers.py:23-24, 27-34`. That is a self-inflicted 10x throughput hit on the primary operator surface.

4. **Evidence:** The only documented stress data already admits a narrow operating envelope. `submission/14_stress_test_summary.md:17-23` says the 20x20 case reaches only `0.204` average visited coverage and is "not ready". `submission/14_stress_test_summary.md:25-36` says 8 peers on 10x10 takes `30.76s` wall and `140252 KB` max RSS. The repo search for common perf/load tooling (`benchmark`, `lighthouse`, `playwright`, `k6`, `locust`, `pytest-benchmark`, `hyperfine`) returned no in-repo matches.
   **Inference:** Performance claims are frozen in prose, not enforced by automation. Regressions in startup time, polling cadence, CPU, or memory can land silently.

5. **Evidence:** The automated test surface is shallow relative to the implementation surface. A read-only line count across active source roots shows about `12110` source lines versus `2111` test lines (`0.174` test/source ratio). The top runtime-heavy files are `simulation/peer_runtime.py` (775), `simulation/stub.py` (757), `runtime/run.ts` (518), and `runtime/config.ts` (379). Yet `tests/test_run_local_peers.py:33-50` only checks Ctrl-C cleanup, and `tests/test_peer_runtime.py:37-63` only verifies six ticks, peer visibility, and nonnegative coverage. A search across `tests/`, `tests_ros/`, dashboard tests, and `entropy_hunt_ui.test.mjs` found no direct references to `runtime/run.ts`, `runtime/config.ts`, `runtime/health.ts`, `runtime/ports.ts`, `runtime/processes.ts`, `runtime/hunt.sh`, `runtime/hunt-monitor.sh`, or `runtime/clean.ts`.
   **Inference:** The highest-risk path — the Bun-first launcher/orchestrator that the README tells users to run first — is the least defended path in the suite.

6. **Evidence:** Frontend verification is aimed at source demos, not shipped surfaces. `entropy_hunt_ui.test.mjs:126-260` loads and inspects `entropy_hunt_v2.html` / `entropy_hunt_mockup.html` directly. `tests/test_frontend_build.py:8-21` only checks that packaged files exist and that one string appears in `dist/index.html`.
   **Inference:** The package step can break `dist/console.html`, `dist/mockup.html`, or `dist/index.html` behavior while leaving the main JS test suite green.

7. **Evidence:** The repo carries obvious simplification debt. Shared replay/entropy logic exists twice: `entropy_hunt_v2.html` defines `H`, `applyReplayPayload`, `maxEntropyCell`, `assignTargets`, `coverage`, and `drawGrid` at `:564, :718, :793, :888, :1012, :1032`, while `entropy_hunt_mockup.html` redefines the same concepts at `:320, :368, :337, :430, :526, :484`. `demo.typescript` is a `6844`-line terminal transcript with no in-repo references. The workspace also carries heavyweight generated artifacts: `build/` is `207M`, `runtime/sessions/` is `8.5M`, and the checked-in peer-run directories add multiple more megabytes.
   **Inference:** A 20% LOC / repo-weight reduction is achievable without cutting capability: remove dead transcripts, stop storing generated session/build artifacts in the main tree, and deduplicate the two HTML consoles around a shared logic module.

### Explicit missing parity list
- No automated proof that the Bun-first launcher path behaves the same as the direct Python peer launcher.
- No automated perf parity guardrail for startup time, snapshot freshness, RSS, CPU, or polling latency.
- No automated deployment parity between docs, tests, `vercel.json`, and `package.json`.
- No packaged-frontend behavior parity tests for `dist/index.html`, `dist/console.html`, and `dist/mockup.html`.
- No evidence that the advertised verification command set is green on a clean checkout without manual excludes.

### Hidden logic risks
- Monitor-on changes runtime speed semantics because it appears to alter tick delay, not just presentation.
- Verification can silently exclude or include generated ROS build artifacts depending on local state.
- Packaging can drift from source-console behavior because tests mostly exercise source HTML, not built output.
- Stress readiness is being inferred from prose summaries rather than enforced ceilings.

### Frontend failures relevant to this lane
- Packaging tests are existence checks, not behavior checks.
- Two consoles duplicate critical replay/entropy logic, increasing regression probability.
- The QA checklist is manual and still npm-oriented while package deploy scripts are bun-oriented.

### Performance blind spots
- No benchmark harness, load test, or perf regression budget is wired into the repo.
- No startup-time or steady-state latency assertions exist for the default Bun launcher path.
- Stress evidence stops at a handwritten markdown summary rather than a reproducible automated gate.
- Repo-weight bloat (`build/`, session captures, peer-run dumps, transcript logs) increases clone/index time without improving runtime capability.

### Simplification opportunities (~20% without losing capability)
- Remove or relocate `demo.typescript` and generated run/build/session artifacts from the main repo surface.
- Extract shared logic from `entropy_hunt_v2.html` and `entropy_hunt_mockup.html` into one module.
- Collapse the deploy contract to one toolchain (`npm` or `bun`) and align docs/tests/scripts.
- Add explicit excludes for generated ROS build output instead of pretending `mypy .` is stable against build debris.
- Trim launcher wrapper sprawl by testing one canonical entrypoint instead of maintaining multiple lightly-verified shells.

## 2026-04-06 Read-only audit follow-up

8. **Evidence:** The live snapshot path does full disk re-merge work on every request. `scripts/serve_live_runtime.py:24-31` rereads every `*.json` file, `:34-115` re-merges all drones/events/grid cells, and `:137-150` does that same merge even for `/state` and `/events`. At the same time, `entropy_hunt_v2.html:726-748` polls `/snapshot.json` every `1000` ms and the OpenTUI defaults to `400` ms polling in `dashboard/tui_theme.ts:134-140`.
   **Inference:** Live operator polling cost scales with peer-count × grid-size × event-volume, with no caching, no incremental merge, and no latency budget. As runs get larger, the observability surface itself becomes a throughput hazard.

9. **Evidence:** Runtime readiness is defined far too loosely for a multi-peer port. `runtime/health.ts:4-18,40-42` declares readiness after just one JSON file appears and one HTTP fetch succeeds. That ignores requested peer count, BFT activity, or snapshot freshness.
   **Inference:** The launcher can report a "ready" system while only a fragment of the intended swarm is actually alive, which makes load/startup timing numbers misleading and masks partial-start failure modes.

10. **Evidence:** The packaged shell is more of a file copier than a verified product build. `scripts/build_frontend.py:100-126` copies `entropy_hunt_v2.html` and `entropy_hunt_mockup.html` straight into `dist/`, while `frontend/index.template.html:44-48` still embeds npm-based operator commands. `tests/test_frontend_build.py:8-21` only verifies file existence plus one string in `index.html`.
    **Inference:** The "build" step does not materially validate packaged behavior, and the packaged surface can preserve stale operational instructions even when the source of truth changes.

