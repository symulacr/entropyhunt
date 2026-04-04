# Entropy Hunt

## Claude Code Build Handoff — Vertex Swarm Challenge 2026, Track 2

**Hackathon:** [Vertex Swarm Challenge 2026](https://dorahacks.io/hackathon/vertex-swarm-challenge-2026)
**Track:** Track 2 | Search & Rescue Swarms ($10,000 prize pool)
**Submission deadline:** 2026-04-06 10:00 UTC
**GitHub guide:** https://github.com/tashigit/vertex-hackathon-guide
**Simulation:** Webots R2023b (free, open source — https://cyberbotics.com)
**Discord submission channel:** https://discord.com/channels/1011889557526032464/1483341393052176526
**Tashi docs:** https://tashi.network/

---

## What This Is

A 5-drone search coordination system where the swarm's collective next action is always: send the next available drone to the zone of highest joint uncertainty — maximum information entropy. No pre-assigned grid sectors. No central planner. No ROS master node. The search pattern is not programmed; it emerges from the swarm's shared certainty state.

The coordination problem is genuine: when two drones simultaneously lock onto the same high-entropy zone, they must P2P-auction the zone boundary using BFT consensus. The auction output determines which drone takes which sub-zone. Remove Vertex and the auction has no Byzantine-resistant arbitration. Remove FoxMQ and the shared certainty map does not exist.

**Minimum demo requirement:** 5 simulated drones, Webots or equivalent. Mocked sensor data is explicitly permitted by the Track 2 brief. The focus is the mesh coordination logic, not the sensor accuracy.

---

## Why This Is Not "Frontier Exploration With BFT Stickered On"

Frontier-based exploration (Yamauchi 1997) assigns each robot a "frontier" — the boundary between explored and unexplored space — using a centralised cost function. There is one map owner. There is one coordinator.

Entropy Hunt is different in three specific ways:

1. **Decentralised certainty fusion:** Each drone maintains its own local certainty map. These maps are P2P-merged via FoxMQ shared state. No drone is the authoritative map owner. If the drone with the "best" map goes offline, its state survives in the FoxMQ mesh.
2. **BFT-resistant zone auction:** When two drones target the same zone, the split is determined by a BFT round — not by a central scheduler, not by first-come-first-served (which is gameable). The auction outcome is verified by all peers.
3. **Certainty decay:** A zone searched 60 seconds ago becomes less certain over time (modelled as exponential decay). The swarm re-hunts stale certainty zones autonomously. This is not a feature of frontier exploration — it is inherent to the information-theoretic model.

---

## Core Mechanism

### The Certainty Map

A 2D grid of `N × N` cells (recommend 10×10 for demo — 100 cells, 5 drones, coverage ratio is clear). Each cell:

```python
@dataclass
class CellState:
    x: int
    y: int
    certainty: float      # 0.0 = completely unknown, 1.0 = fully searched
    last_updated_ms: int  # Unix timestamp ms
    updated_by: str       # peer_id of last drone to update
    decay_rate: float     # 0.001 per second — certainty decays toward 0.5 when stale
```

**Certainty update rule:** When drone D is in cell (x,y) for one simulation tick:
`cell.certainty = min(1.0, cell.certainty + 0.05)`

**Certainty decay rule (applied every second to all cells):**
`cell.certainty += decay_rate * (0.5 - cell.certainty)`
(Certainty decays toward 0.5 — maximum entropy — not toward 0. An old observation is uncertain, not unknown.)

### Information Entropy Per Cell

`H(cell) = -p * log2(p) - (1-p) * log2(1-p)`
where `p = cell.certainty`.

Maximum entropy is at `certainty = 0.5` (H = 1.0 bit). Fully searched (certainty = 1.0) and fully unknown (certainty = 0.0) are both zero entropy — the swarm is either certain it's empty or certain it's unsearched. The interesting zone is the uncertain middle.

**Greedy zone selection:** Each drone computes `argmax H(cell)` over all cells not currently claimed by another drone. This is each drone's independent estimate of where to go next. No communication needed for the selection itself — only for the claim lock.

### Zone Auction Protocol

This is the genuine coordination problem. Two drones independently compute the same max-entropy cell and send simultaneous CLAIM messages.

**Without BFT:** First-come-first-served. Gameable. Race condition on network latency. Not Byzantine-resistant.

**With BFT:**

1. Both Drone A and Drone B publish CLAIM for cell (3,7) to `swarm/zone_claims`
2. FoxMQ delivers both claims to all 5 peers
3. BFT round is triggered: all online drones vote on which claim is valid (timestamp precedence + drone proximity to cell as tiebreaker)
4. BFT output: Drone A gets (3,7), Drone B gets second-highest entropy cell
5. Both drones receive the confirmed assignment and begin transit

**Zone split (advanced):** If two drones are equidistant to the contested cell, BFT can split it: Drone A gets left half, Drone B gets right half. This is the emergent Voronoi partition behaviour — not programmed, produced by the auction.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                   FoxMQ Mesh                          │
│                                                       │
│  swarm/certainty_map    — full grid, replicated       │
│  swarm/drone_state/{id} — position, role, zone       │
│  swarm/zone_claims      — claim events (BFT input)   │
│  swarm/bft_round/{n}    — BFT round outputs           │
│  swarm/heartbeat/{id}   — 1Hz pulse per drone        │
│  swarm/survivor_found   — target detection events    │
└──────────────────────────────────────────────────────┘

Drones (Vertex 2.0 P2P nodes, all peers):
  Drone_1  Drone_2  Drone_3  Drone_4  Drone_5
     │        │        │        │        │
     └────────┴────────┴────────┴────────┘
          Vertex 2.0 peer discovery mesh
```

Each drone process runs:

- Vertex 2.0 node (P2P discovery, heartbeat)
- FoxMQ subscriber (certainty map, claims, BFT)
- FoxMQ publisher (own state, own claims, own heartbeat)
- Zone selector (local entropy computation)
- Claim handler (BFT round participation)
- Webots controller (movement commands — or stub if pure Python sim)

---

## Drone State Machine

```
IDLE → COMPUTING (entropy argmax) → CLAIMING (BFT round)
                                         │
                              ┌──────────┴──────────┐
                         CLAIM_WON             CLAIM_LOST
                              │                     │
                          TRANSITING           COMPUTING (next)
                              │
                          SEARCHING (incrementing certainty)
                              │
                      ZONE_COMPLETE (certainty > 0.95)
                              │
                           IDLE
```

**Offline/stale state:** If a drone's heartbeat is absent for >3 seconds, all peers mark it `STALE`. Its claimed zone is released back to the claim pool. BFT round confirms the release. The released zone certainty is set to its current decay-computed value — no manual reset.

---

## Tech Stack

**Language:** Python 3.11+ (or Rust for the Vertex core node, Python for the controller logic)
**P2P / Messaging:** Vertex 2.0 + FoxMQ (via Tashi SDK — see hackathon guide)
**Simulation:** Webots R2023b (free: https://cyberbotics.com/doc/guide/installation-procedure)

- Recommended drone model: Mavic 2 (included in Webots default library)
- Alternatively: custom e-puck for ground robots, or pure Python grid simulation (no Webots)
  **Visualisation:** `matplotlib` for the entropy heat map, updated every 2 seconds
  **Logging:** `structlog` for structured JSON event logs

**Search terms for additional resources:**

- `webots python controller tutorial`
- `webots mavic 2 pro python controller`
- `foxmq tashi python sdk github`
- `vertex 2.0 p2p node python`
- `shannon entropy numpy python`
- `information theory bayesian search theory`
- `frontier based exploration robotics yamauchi 1997` (for counter-argument context)
- `byzantine consensus distributed systems python`

---

## File Structure

```
entropy-hunt/
├── README.md
├── requirements.txt
├── webots_world/
│   ├── entropy_hunt.wbt      # Webots world file (flat arena, 5 drones)
│   └── protos/               # Drone proto files if custom
│
├── core/
│   ├── certainty_map.py      # CellState grid, entropy computation, decay
│   ├── zone_selector.py      # argmax H(cell), exclusion of claimed zones
│   ├── mesh.py               # FoxMQ pub/sub wrappers
│   ├── bft.py                # BFT round management, vote collection
│   └── heartbeat.py          # 1Hz pulse publisher, stale detection
│
├── roles/
│   ├── searcher.py           # Zone selection, transit, certainty update
│   └── claimer.py            # Claim publication, BFT participation
│
├── auction/
│   ├── protocol.py           # Zone auction logic, split computation
│   └── voronoi.py            # Optional: visualise emergent zone partitions
│
├── simulation/
│   ├── stub.py               # Pure Python grid sim (no Webots needed for CI)
│   └── webots_bridge.py      # Webots supervisor API → drone position updates
│
├── viz/
│   └── heatmap.py            # matplotlib live entropy grid visualisation
│
├── failure/
│   └── injector.py           # Kill drone N after T seconds (demo failure injection)
│
└── main.py                   # Entry: --drones 5 --grid 10 --duration 180
```

---

## Build Order (Execute in Sequence)

### Step 1 — Vertex handshake and heartbeat

Follow https://github.com/tashigit/vertex-hackathon-guide. Start 2 Python Vertex nodes. Exchange signed hello. Implement 1Hz heartbeat on `swarm/heartbeat/{id}`. Implement stale detection (no heartbeat for 3s → mark peer STALE). This is the Warm-Up track exercise — complete it first and submit to Discord for the daily bounty.

### Step 2 — FoxMQ certainty map

Implement `core/certainty_map.py`. Initialise a 10×10 grid (all certainty = 0.5 — maximum entropy at start, since nothing is known). Publish the full grid to `swarm/certainty_map` from Drone_1. Confirm Drone_2 receives it and can compute entropy values. Implement the decay function. Test: let grid sit idle for 30 seconds. Confirm all cells with certainty > 0.5 have decayed toward 0.5.

### Step 3 — Zone selector

Implement `core/zone_selector.py`. Input: current certainty map + set of claimed zones. Output: `(x, y)` of max entropy cell not currently claimed. Test with a partially-searched grid: confirm the selector always returns the least certain unclaimed cell. Edge case: all cells at maximum certainty (search complete) → return None, drone goes IDLE.

### Step 4 — BFT claim lock (no contention case first)

Implement claim publication to `swarm/zone_claims`. Implement BFT round where all peers acknowledge a claim with no competitor. Confirm all 5 drones agree that Drone_1 owns cell (3,7). This is the no-contention baseline.

### Step 5 — BFT claim lock (contention case)

Simultaneously submit two CLAIM messages for the same cell from Drone_1 and Drone_2. Trigger BFT round. BFT must produce exactly one winner. Implement tiebreaker: drone closest to the contested cell wins (use Euclidean distance from current drone position). If equidistant: implement zone split. Test determinism: run the same contention 10 times, confirm same winner each time given same positions.

### Step 6 — Webots integration (or stub)

If using Webots: implement `simulation/webots_bridge.py`. Use the Webots Supervisor API to read drone positions and send movement commands. The controller script runs inside Webots; it calls `searcher.py` to get the next zone and moves the drone there.

If not using Webots: implement `simulation/stub.py`. A grid where drone positions are integers, movement is teleport (one cell per tick), and "searching" means incrementing certainty for the current cell. This is sufficient for the coordination demo — the brief explicitly says "Use mocked sensor data."

### Step 7 — Live entropy heatmap

Implement `viz/heatmap.py` using `matplotlib.animation`. 10×10 grid, cell colour from white (certainty 1.0) to dark grey (certainty 0.5, maximum entropy) to black (certainty 0.0). Drone positions as coloured dots. Zone ownership boundaries as thin lines. This is your submission video visual.

### Step 8 — Failure injection

Implement `failure/injector.py`. After 60 seconds of running, call `os.kill(drone_2_pid, SIGKILL)` (or disconnect its Vertex node). All peers detect the absent heartbeat after 3 seconds and mark Drone_2 STALE. Drone_2's claimed zone is released via BFT round. A surviving drone claims it. The heatmap shows no interruption in coverage.

### Step 9 — Survivor simulation

Implement a "survivor found" event. When any drone reaches certainty > 0.95 in a designated target cell (pre-seeded), it publishes to `swarm/survivor_found` with coordinates and confidence. All other drones receive the event. The demo ends.

### Step 10 — Demo run

```bash
python main.py --drones 5 --grid 10 --duration 180 --target 7,3 --fail drone_2 --fail-at 60
```

Expected output: certainty map shows full coverage, survivor found event printed, failure injection and recovery logged, final certainty map saved to `final_map.json`.

---

## Demo Script (For Submission Video)

**Duration:** 3.5 minutes max.

1. `[0:00]` Start 5 drone processes. Show Vertex P2P discovery in logs (each drone prints peer list). Show initial entropy heatmap — all cells medium grey (certainty 0.5, max entropy).
2. `[0:40]` Drones begin selecting zones. Show the heatmap: cells lighten as drones search them. Show entropy values decreasing in real time.
3. `[1:20]` Contention event: two drones target the same zone simultaneously. Show BFT round in logs. Show the auction winner in the drone state table. Show the losing drone immediately select the next zone.
4. `[2:00]` Kill Drone_2 (packet loss simulation or direct kill). Show heartbeat timeout in logs after 3 seconds. Show BFT zone release. Show Drone_4 claiming Drone_2's zone. Heatmap search continues without interruption.
5. `[2:40]` Survivor found event: one cell reaches certainty 0.95. Drone announces to swarm. All drones receive event. Show the `swarm/survivor_found` message in logs.
6. `[3:00]` Print final certainty map. Show coverage percentage. Show total BFT rounds executed. Show node dropout and recovery count.

---

## Judging Criteria Mapping

| Criterion                                | How This Submission Satisfies It                                                                       |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Mesh Survival                            | Drone dropout → heartbeat timeout → BFT zone release → surviving drones continue without interruption  |
| Peer discovery under network constraints | Vertex 2.0 handles; demonstrate with synthetic packet loss (Webots network plugin or Linux `tc netem`) |
| Decentralised logic                      | No central ROS master, no scheduler — zone selection is local entropy computation, confirmed via BFT   |
| Zero reliance on single ROS master node  | ROS is not used. Pure Vertex 2.0 + FoxMQ.                                                              |
| Robustness                               | Failure injection at T=60s, recovery demonstrated, coverage does not regress                           |
| Developer Clarity                        | README with run instructions, live heatmap as demo visual, structured logs                             |

---

## Synthetic Packet Loss Setup (For Robustness Criterion)

On Linux (required for Track 2 "severe network constraints" criterion):

```bash
sudo tc qdisc add dev lo root netem loss 20% delay 100ms
```

Run your demo under this condition. Show that BFT rounds still complete (they will take longer but succeed). Remove after demo:

```bash
sudo tc qdisc del dev lo root
```

Search terms: `linux tc netem packet loss tutorial`, `network emulation linux tc qdisc`

---

## Judge Attacks and Pre-Emptions

**"Frontier-based exploration is 30 years old."**
Your answer: "Entropy Hunt is not frontier exploration. Frontier exploration requires a central map owner and a global cost function. Entropy Hunt uses P2P-merged certainty maps with BFT-resistant zone auctions. The coordination mechanism — not the search heuristic — is the submission. Frontier exploration has no equivalent of the BFT claim lock or the emergent Voronoi zone partition."

**"Your 'entropy' is just inverse coverage percentage."**
Your answer: "Shannon entropy is not inverse coverage. At certainty = 0.0 or 1.0, H = 0. At certainty = 0.5, H = 1.0 bit. The decay function pushes searched zones toward 0.5 (maximum entropy), not toward 0.0. This means the swarm re-hunts stale zones — a behaviour not possible with coverage-percentage targeting." Show the decay function in your README.

**"Webots simulation with mocked sensors is not realistic."**
Your answer: Quote the Track 2 brief verbatim: "Use mocked sensor data if it helps you focus on the mesh networking." This is not a sensor demo. It is a coordination demo. The brief says this explicitly.

---

## Key External Resources

- Vertex hackathon guide: https://github.com/tashigit/vertex-hackathon-guide
- Webots download: https://cyberbotics.com/doc/guide/installation-procedure
- Webots Python API: https://cyberbotics.com/doc/reference/robot
- FoxMQ SDK: search `foxmq tashi sdk python github`
- Shannon entropy in Python: `scipy.stats.entropy` or implement directly with numpy
- `tc netem` packet loss docs: search `linux tc netem delay loss tutorial`
- Tashi Discord: https://discord.gg/T7rVYWam
- Submission channel: https://discord.com/channels/1011889557526032464/1483341393052176526
- Webots Mavic 2 controller example: search `webots mavic 2 python controller example`
- BFT in Python: search `practical bft python implementation github`
- Search: `information theoretic search coverage python`, `entropy based exploration swarm robotics`

---

## Notes for Claude Code Agent

- Implement `core/certainty_map.py` first and test it in isolation before connecting to Vertex/FoxMQ. The entropy math is simple — do not overcomplicate it.
- The FoxMQ certainty map should transmit the full grid as JSON on every update. At 10×10 = 100 cells, this is ~4KB per message — acceptable. For 20×20, consider delta compression (only send changed cells).
- The BFT round for zone claims does not need to implement full pBFT. A simpler signed-vote majority is sufficient: each peer signs its vote, claims are validated by checking 3-of-5 (or N/2+1) signatures. The Tashi SDK likely provides a convenience wrapper — check the hackathon guide.
- Webots is optional. A pure Python grid simulation (`simulation/stub.py`) is faster to build and sufficient for the coordination demo. Only add Webots if time permits after the coordination logic is complete and stable.
- The `matplotlib` heatmap must update live without blocking the async event loop. Use `plt.pause(0.1)` in a separate thread or use `matplotlib` in non-interactive mode with file output if threading is problematic.
- The demo run must terminate cleanly and print a summary. Judges will run it. A demo that hangs or crashes on exit is a deduction.
- Target 10×10 grid, 5 drones, 180 second run. Full coverage is achievable in under 120 seconds. The remaining 60 seconds shows the decay and re-search behaviour.
- If Vertex SDK is not yet available as a Python package, use the C bindings via `ctypes` or run the Vertex node as a subprocess and communicate via stdin/stdout. The hackathon guide covers this.
- Search `tashi vertex python ctypes` if direct SDK is unavailable.

---

## Prototype Audit and Production Handoff

The two HTML files in this directory are **UI prototypes**, not the production implementation. They are useful for visual direction and demo scripting, but they currently simulate the swarm locally in inline JavaScript. Treat them as throwaway references unless a production pass extracts their logic into tested modules.

### Audited Files

| File                       | Current role             | What it proves                                                  | What it does **not** prove                                                        |
| -------------------------- | ------------------------ | --------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `entropy_hunt_mockup.html` | Minimal operator console | Layout, metric hierarchy, entropy-map framing                   | Real Vertex/FoxMQ integration, deterministic auctioning, deployable app structure |
| `entropy_hunt_v2.html`     | Richer demo mockup       | Failure-injection controls, hover affordances, denser telemetry | Real network fault handling, reusable state model, modular frontend architecture  |
| `entropy_hunt.md`          | Product + build handoff  | Problem framing, system design, demo script, judging alignment  | Implementation status, prototype caveats, deployment checklist                    |

### Current cleanup status (2026-04-04)

- Both HTML prototypes now include local `:root` token defaults so they render coherently outside the original shell.
- `entropy_hunt_mockup.html` now resolves auction winners deterministically (nearest drone, then lexical drone id) instead of relying on random selection.
- The mockup metrics derive coverage/entropy from computed grid totals, and recovery paths randomise `x`/`y` independently during respawn.

### Concrete Review Findings

1. **Prototype logic diverged from the written spec.**
   - The markdown describes deterministic BFT claim resolution using timestamp precedence and proximity. The prototypes were simulating auctions inline and, before cleanup, could report misleading round counts or random-looking outcomes.
   - Action: keep the UI copy aligned with the implementation contract. If the frontend is only a mockup, label synthetic behaviour explicitly.

2. **Standalone rendering needed local design-token fallbacks.**
   - Both HTML files referenced `var(--color-*)` and font tokens that only work when a parent shell injects Anthropic-style variables.
   - Action: provide local `:root` defaults in prototypes, then replace them with app-level design tokens when the production shell exists.

3. **Two demo-state bugs undermined operator trust.**
   - Reconnect/revive flows reused `y = x`, causing diagonal respawns that look like a bug instead of a simulation decision.
   - Canvas drawing used CSS custom-property strings directly in script, which is unreliable for `CanvasRenderingContext2D` colors.
   - Action: keep simulation helpers deterministic and resolve CSS tokens before using them in canvas drawing.

4. **The prototypes are still not production-grade frontend code.**
   - Inline event handlers (`onclick=...`), inline simulation logic, global mutable state, and no tests mean they are unsuitable as the deployed Vercel app.
   - Action: split the production app into:
     - `app/(marketing)/page.tsx` or equivalent landing surface
     - `components/entropy-console/*` for presentation
     - `lib/sim/*` for deterministic local demo logic
     - `lib/mesh/*` for real Vertex/FoxMQ integration
     - `lib/contracts/*` for shared swarm-state types

### Production Readiness Checklist

- [ ] Move entropy math, cell ownership, and auction selection into testable modules.
- [ ] Replace inline DOM mutation with framework state updates or a small view-model layer.
- [ ] Make BFT status labels honest: `synthetic`, `simulated`, or `live mesh`.
- [ ] Remove all hard-coded `10×10 = 100 cells` assumptions; derive totals from config.
- [ ] Add a real deployment entrypoint (`package.json`, build command, Vercel config if needed).
- [ ] Add smoke tests for: coverage calculation, auction winner selection, revive/dropout handling, and survivor detection.
- [ ] Keep the markdown handoff in sync with whatever actually ships.

### Recommended Vercel Delivery Order

1. Ship a static explanatory landing page first (`entropy_hunt.md` -> README/marketing copy).
2. Ship the standalone simulated console second (no live mesh, clearly labelled as a prototype/demo).
3. Add a server/API boundary only when real swarm events exist to stream into the UI.
4. Do **not** claim live Vertex/FoxMQ support in the deployed UI until the data path is real and observable.
