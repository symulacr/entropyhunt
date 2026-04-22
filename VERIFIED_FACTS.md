# VERIFIED_FACTS.md

> Brutal audit of README.md claims against the source code.  
> Last updated: 2026-04-22

---

## 1. Description (line 5)

**Claim:** *"Drones partition terrain via Voronoi cells, resolve conflicts through Byzantine-fault-tolerant consensus over a P2P mesh, and emit cryptographically signed coordination proofs."*

### 1a. Voronoi cells
**STATUS: INACCURATE**

- **File:** `auction/voronoi.py`
- **Lines:** 23–64 (`ownership_grid`), 66–83 (`partition_grid`)
- **Reality:** The code uses a **BFS flood-fill** with **Manhattan distance** to assign grid cells to the nearest drone, with tie-breaking by `drone_id` lexical order. This is a grid-based nearest-neighbor assignment, **not** a Voronoi tessellation (which requires Euclidean distance and produces polygonal cells).
- **Correction needed:** Change to "grid-based terrain partitioning" or "Manhattan-distance cell assignment."

### 1b. Byzantine-fault-tolerant consensus
**STATUS: EXAGGERATED / INACCURATE**

- **File:** `core/consensus.py`
- **Lines:** 47–61, 174–186, 301–307
- **Reality:** The implementation is **simple majority voting** with `quorum = len(peer_ids) // 2 + 1` (line 302). There is **no Byzantine Fault Tolerance**:
  - No cryptographic verification of votes (votes are plain JSON payloads).
  - No protection against equivocation, Sybil attacks, or malicious voters.
  - No PBFT-style prepare/commit/view-change phases.
  - If the mesh delivers bad votes, the code simply counts them.
- **Correction needed:** Change "Byzantine-fault-tolerant consensus" to "majority-vote conflict resolution" or "quorum-based consensus."

### 1c. Cryptographically signed coordination proofs
**STATUS: INACCURATE**

- **File:** `simulation/proof.py`
- **Lines:** 204–222 (`compute_peer_signatures`)
- **Reality:** The "proofs" are **SHA-256 hashes of sorted JSON event logs per peer**. There is **no asymmetric cryptography**, no private-key signing, no PKI, and no digital signature scheme. The mesh uses **HMAC-SHA256** (a shared-secret MAC, not a signature) for message integrity (`core/mesh.py` lines 102–122).
- **Correction needed:** Change to "HMAC-authenticated mesh messages" and "cryptographic audit hashes" (not signatures).

---

## 2. Quickstart (lines 14–19)

**Claim:** `cp .env.example .env` then `./setup.sh && ./demo.sh`

**STATUS: MIXED**

- `setup.sh` (line 132–136) and `demo.sh` exist and function as described.
- However, `.env.example` was **not found** in the repo root during this audit (the setup script warns if it is missing: line 138). The README should note that `.env.example` may need to be created manually.
- **Correction needed:** Add fallback instruction if `.env.example` is absent.

---

## 3. Demo commands (lines 24–26)

**STATUS: ACCURATE**

- `./demo.sh --duration 60 --drones 5 --grid 8` — supported (`demo.sh` lines 279–310).
- `./demo.sh --tui` — supported (`demo.sh` line 292–294, 446–474).
- `python3 main.py --mode stub --packet-loss 0.3 --fail drone_2 --fail-at 15` — all flags exist (`main.py` lines 36, 50, 68, 49).

---

## 4. Architecture diagram (lines 31–40)

**STATUS: PARTIALLY INACCURATE**

### 4a. Mesh → Bridge Rust via UDP
**INACCURATE.**
- `core/bridge.py` lines 56–63 show the Python `VertexBridge` spawns the Rust binary and communicates via **stdin/stdout JSON lines** (pipes), not UDP.
- The Rust node (`vertex-node/src/lib.rs` lines 293–367) does read from stdin and relay over UDP, but the **Python→Rust link is not UDP**.

### 4b. Bridge → multicast Network
**ACCURATE.**
- `vertex-node/src/lib.rs` lines 300, 341–351, 418–438 confirm UDP multicast to `239.255.0.1:9001`.

### 4c. Core → BFT Consensus / Core → Voronoi Auction
**MISLEADING.**
- As noted in §1b and §1a, these are not BFT or true Voronoi.

---

## 5. Architecture table (lines 42–48)

| Claim | Status | Evidence |
|---|---|---|
| Frontend HTML/CSS/JS | **UNVERIFIED** from the 8 files (likely exists elsewhere) | — |
| TUI Monitor TypeScript/Bun | **ACCURATE** | `demo.sh` lines 460–463 runs `bun dashboard/tui_monitor.ts` |
| Core Python 3.12+ | **PARTIALLY INACCURATE** | `setup.sh` line 79 accepts **Python 3.10+**; 3.12 is only recommended. |
| Bridge Rust / tokio | **ACCURATE** | `vertex-node/src/lib.rs` uses `tokio` throughout. |
| Sim Webots / ROS2 | **ACCURATE** | `simulation/webots_controller.py` and `ros2_ws/` exist. |

**Correction needed:** Change Python badge/requirement from "3.12+" to "3.10+ (3.12 recommended)."

---

## 6. Track Compliance table (lines 50–61)

### 6a. Autonomous terrain partitioning → `auction/voronoi.py`
**STATUS: INACCURATE (see §1a)**
- The file does terrain partitioning, but it is **not Voronoi**.

### 6b. BFT consensus → `core/consensus.py`
**STATUS: INACCURATE (see §1b)**
- The file implements majority voting, **not BFT**.

### 6c. 30% failure resilience → `failure/network_injector.py` + demo
**STATUS: MISLEADING / EXAGGERATED**

- **File:** `failure/network_injector.py`
- **Reality:** This file only injects **packet loss and jitter** (lines 21–23, 43–44, 72–73). It does **not** simulate node failures.
- Node failures are handled by `failure/injector.py`, which supports **only a single scheduled drone failure** (`FailurePlan` with one `drone_id` and `fail_at_seconds`). With the default swarm of 5 drones, that is **20% node failure tolerance**, not 30%.
- The "30%" figure appears to come from the demo flag `--packet-loss 0.3`, which is **network degradation**, not failure resilience.
- **Correction needed:** Change to "packet-loss simulation up to 100%" and "single-node failure recovery (~20% with 5 drones)."

### 6d. Cryptographic audit trail → `scripts/verify_poc.py`
**STATUS: PARTIALLY INACCURATE**

- **File:** `scripts/verify_poc.py`, `simulation/proof.py`
- **Reality:** The audit trail exists and is verified (lines 9–49 in `verify_poc.py`), but it uses **SHA-256 hashes of event logs**, not digital signatures. The verification recomputes hashes and compares them — there is no public-key cryptography.
- **Correction needed:** Change "cryptographic audit trail" to "verifiable audit trail with peer-specific SHA-256 hashes."

### 6e. P2P mesh transport → `core/mesh.py` — 4 bus implementations
**STATUS: MOSTLY ACCURATE**

- **File:** `core/mesh.py`
- **Classes:**
  1. `InMemoryMeshBus` (line 178) — in-process
  2. `NullBus` (line 306) — no-op stub (inherits InMemory)
  3. `VertexMeshBus` (line 334) — Rust bridge
  4. `LocalPeerMeshBus` (line 473) — UDP unicast + multicast discovery
  5. `FoxMQMeshBus` (line 702) — MQTT broker
- There are **5 classes**, but only **4 meaningful transport backends** (NullBus is a test stub). However, only `LocalPeerMeshBus` and `VertexMeshBus` are truly P2P; `FoxMQMeshBus` uses a central broker and `InMemoryMeshBus` is local-only.
- **Correction needed:** Clarify that there are 4 backends (in-process, UDP, MQTT, Rust bridge) but only 2 are P2P.

### 6f. ROS2 bridge → `ros2_ws/` QoS topics
**STATUS: ACCURATE**
- `ros2_ws/` contains QoS config (`qos.py`), message definitions, and launch files.

### 6g. Webots physics → `simulation/webots_controller.py`
**STATUS: ACCURATE**
- File exists and wraps the Webots controller API.

### 6h. Multi-language stack → Python + Rust + TypeScript
**STATUS: ACCURATE**
- All three languages are present in the codebase.

---

## 7. Config table (lines 71–77)

| Variable | Claim | Status | Evidence |
|---|---|---|---|
| `ENTROPYHUNT_MESH_SECRET` | HMAC key for mesh messages | **ACCURATE** | `core/mesh.py` lines 85–92, 102–122 |
| `ENTROPYHUNT_HOST` | Bind address for peers | **ACCURATE** | `core/mesh.py` line 483 |
| `ENTROPYHUNT_MQTT_HOST` / `PORT` | FoxMQ broker | **ACCURATE** | `core/mesh.py` lines 723–724 |
| `ENTROPYHUNT_TRANSPORT` | Backend: `local` or `foxmq` (use `--mesh real` for Vertex) | **INCOMPLETE** | `main.py` line 46 shows `--mesh local/real`; line 63 shows `--transport local/foxmq`. The Vertex backend is selected via `--mesh real`, not `ENTROPYHUNT_TRANSPORT`. Also, `local` transport is UDP (LocalPeerMeshBus), not just "local". |

**Correction needed:** Update description to mention Vertex is via `--mesh real`, and clarify that `local` means UDP P2P.

---

## 8. `core/mesh.py` — deep-dive

| Claim in README | Line(s) in mesh.py | Verdict |
|---|---|---|
| Bus count = 4 | 178, 306, 334, 473, 702 | **5 classes, 4 backends** (NullBus is a stub). Acceptable but imprecise. |
| Transport options | — | **In-process, UDP, MQTT (FoxMQ), Rust bridge** — all present. |
| HMAC on messages | 102–122 | **ACCURATE** (`hmac.new(...sha256...)`). |
| P2P discovery | 519–617 (`start_discovery`, `_discovery_loop`) | **ACCURATE** for `LocalPeerMeshBus` (multicast HELLO on `239.255.0.1:9002`). |

---

## 9. `core/consensus.py` — deep-dive

| Claim | Line(s) | Verdict |
|---|---|---|
| BFT implementation | 302 (`quorum = len(peer_ids) // 2 + 1`) | **NOT BFT.** Simple majority quorum. No byzantine tolerance. |
| Vote collection over mesh | 188–232 (`_collect_quorum_votes`) | **ACCURATE** — polls mesh for votes with timeout. |
| Conflict resolution | 247–252 (`resolve_conflict` from `auction.protocol`) | **ACCURATE** — delegates to auction logic. |

---

## 10. `vertex-node/src/lib.rs` — deep-dive

| Claim | Line(s) | Verdict |
|---|---|---|
| HMAC endpoints | 101–119 (`sign_envelope`), 121–148 (`verify_envelope`), 262–269 (`create_app` routes `/hmac/sign` and `/hmac/verify`) | **ACCURATE** |
| UDP multicast | 300, 341–351, 418–438 | **ACCURATE** (`239.255.0.1:9001`) |
| Peer registry | 38–79 (`PeerRegistry`), 163–169 (`health_handler`), 177–188 (`peers_handler`) | **ACCURATE** |
| tokio runtime | 6, 16–17, 272–291 | **ACCURATE** |

---

## 11. `simulation/stub.py` — deep-dive

| Claim | Line(s) | Verdict |
|---|---|---|
| Drone simulation | 62–954 (`EntropyHuntSimulation`) | **ACCURATE** — full tick-based simulation with movement, consensus, heartbeats, and failure injection. |
| Survivor found logic | 691–714 | **ACCURATE** — publishes `swarm/survivor_found` when target certainty threshold reached. |
| Failure injection | 601–621 (`_inject_failure`) | **ACCURATE** — delegates to `FailureInjector` (single-drone only). |

---

## 12. `main.py` — deep-dive

| Claim | Line(s) | Verdict |
|---|---|---|
| CLI flags and modes | 33–76 (`parse_args`) | **ACCURATE** — `--mode stub/peer`, `--mesh local/real`, `--transport local/foxmq`, `--packet-loss`, `--fail`, `--fail-at`, etc. |
| `--mode stub` | 111–203 (`run_stub_mode`) | **ACCURATE** |
| `--mode peer` | 206–250 (`run_peer_mode`) | **ACCURATE** |

---

## Summary of Required Corrections

| # | README Location | Current Wording | Suggested Correction | Severity |
|---|---|---|---|---|
| 1 | Line 5 | "Voronoi cells" | "grid-based terrain partitioning" | High |
| 2 | Line 5 | "Byzantine-fault-tolerant consensus" | "majority-vote quorum consensus" | High |
| 3 | Line 5 | "cryptographically signed coordination proofs" | "HMAC-authenticated messages and verifiable audit hashes" | High |
| 4 | Line 48 | "Core \| Python 3.12+" | "Core \| Python 3.10+ (3.12 recommended)" | Medium |
| 5 | Line 56 | "30% failure resilience" | "Packet-loss simulation up to 100%; single-node failure recovery" | High |
| 6 | Line 57 | "Cryptographic audit trail" | "Verifiable audit trail with SHA-256 peer hashes" | Medium |
| 7 | Line 58 | "4 bus implementations" | "4 transport backends (in-process, UDP P2P, MQTT, Rust bridge)" | Low |
| 8 | Lines 33–39 (diagram) | "Mesh → Bridge Rust via UDP" | "Mesh → Bridge Rust via stdin/stdout" | Medium |
| 9 | Line 76 | `ENTROPYHUNT_TRANSPORT` description | Add note that Vertex is via `--mesh real`, not this env var | Low |
| 10 | Quickstart | `.env.example` | Add caveat that `.env.example` may need to be created if absent | Low |

---

*End of audit.*
