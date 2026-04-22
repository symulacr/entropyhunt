# COMPLIANCE_AUDIT.md

**Auditor:** Sisyphus-Junior  
**Date:** 2026-04-22  
**Scope:** `docs/COMPLIANCE.md` vs. all referenced source and test files  
**Method:** Line-by-line verification of evidence claims, test existence, and behavioral accuracy.

---

## Executive Summary

| Requirement | Claimed Status | Verified Status | Severity |
|---|---|---|---|
| 1. Multi-agent swarm | PASS | **PASS** | Minor line inaccuracies |
| 2. P2P mesh networking | PASS | **PASS** | **Major mislabeling** of `VertexMeshBus` |
| 3. Decentralized decision-making | PASS | **PASS** | Clean |
| 4. Fault tolerance | PASS | **PASS** | Misleading recovery description |
| 5. Scalability | PASS | **PASS** | Overstated "completion" claim |
| 6. Real-time operation | PARTIAL | **PARTIAL** | Unsubstantiated sub-millisecond claim |
| 7. Deterministic behavior | PASS | **PASS** | False "no stochastic hidden state" claim |
| 8. Cryptographic proof | PASS | **PASS** | Clean |
| 9. SAR relevance | PASS | **PASS** | Clean |
| 10. Demo / reproducibility | PASS | **PASS** | Test count off by 4 |

**Overall:** 9 PASS, 1 PARTIAL — but **4 requirements contain materially inaccurate or overstated evidence lines** that should be corrected before submission to judges.

---

## Requirement 1: Multi-agent swarm (≥3 agents)

**Verified Status:** PASS

### Evidence Accuracy

| Claimed Evidence | Line | Verdict | Notes |
|---|---|---|---|
| `simulation/stub.py:57` — `DroneReplica` class simulates 5+ drones per process | 57 | **INACCURATE** | `DroneReplica` is a simple dataclass (line 57: `class DroneReplica:`). It does not "simulate" anything; the simulation logic is in `EntropyHuntSimulation._build_drones()` and `_move_and_search()`. |
| `simulation/runtime.py:39` — `PeerRuntime` runs one drone per process in peer mode | 39 | **WRONG LINE** | Line 39 is `_QUORUM_STALE_THRESHOLD_MS = 10000`. The `PeerRuntime` class starts at **line 73**. |
| `ros2_ws/.../drone_node.py:70` — `_DroneNodeImpl` ROS2 node | 70 | Correct | `class _DroneNodeImpl(Node):` exists. |
| `simulation/webots_runtime.py:53` — `WebotsPeerRuntime` bridges physics simulation | 53 | Correct | `class WebotsPeerRuntime:` exists. |

### Tests

| Claimed Test | Line | Verdict |
|---|---|---|
| `tests/test_stress.py:34` — 10-drone validation | 34 | Correct. `test_max_drones_10_grid_10` exists and validates 10 drones. |
| `tests/test_break.py:585` — 100-drone no-crash test | 585 | Correct. `test_100_drones_20x20_grid_no_crash` exists. |

### Recommended Corrections
- Change `simulation/stub.py:57` evidence to: `simulation/stub.py:139-146` — `_build_drones()` creates N drone instances.
- Change `simulation/runtime.py:39` to `simulation/runtime.py:73` — `PeerRuntime` class.

---

## Requirement 2: P2P coordination / mesh networking

**Verified Status:** PASS

### Evidence Accuracy

| Claimed Evidence | Line | Verdict | Notes |
|---|---|---|---|
| `core/mesh.py:178` — `InMemoryMeshBus` (deterministic validation) | 178 | Correct | `class InMemoryMeshBus(MeshBusProtocol):` — in-process only, used for tests. |
| `core/mesh.py:334` — `VertexMeshBus` (UDP multicast P2P) | 334 | **FACTUALLY WRONG** | `VertexMeshBus` is **NOT** UDP multicast P2P. It spawns a Rust binary bridge (`core.bridge.VertexBridge`) and falls back to in-process. **UDP multicast P2P is `LocalPeerMeshBus`**, not `VertexMeshBus`. This is the most serious factual error in the document. |
| `core/mesh.py:473` — `LocalPeerMeshBus` (UDP unicast) | 473 | Correct | `class LocalPeerMeshBus(InMemoryMeshBus):` — UDP socket bus. |
| `core/mesh.py:702` — `FoxMQMeshBus` (MQTT over FoxMQ) | 702 | Correct | `class FoxMQMeshBus(InMemoryMeshBus):` — MQTT broker-backed. |
| `simulation/stub.py:752` — "vertex p2p discovery complete" log | 752 | Correct | Log line exists. |
| `core/mesh.py:133-136` — UDP multicast discovery constants | 133-136 | Correct | `_DISCOVERY_GROUP`, `_DISCOVERY_PORT`, etc. |

### Tests

| Claimed Test | Line | Verdict |
|---|---|---|
| `tests/test_integration.py:250` — `TestRealUDPMesh` | 250 | Correct. Tests UDP peer exchange. |
| `tests/test_mesh.py:9` — local peer message exchange | 9 | Correct. `test_local_peer_mesh_bus_exchanges_messages_between_ports`. |
| `tests/test_foxmq_e2e.py:197` — FoxMQ peer mode | 197 | Correct. `test_two_peers_coordinate_via_foxmq`. |

### Recommended Corrections
- **CRITICAL:** Replace `core/mesh.py:334` — `VertexMeshBus` (UDP multicast P2P) with:
  - `core/mesh.py:334` — `VertexMeshBus` (Rust binary bridge with in-process fallback)
  - `core/mesh.py:473` — `LocalPeerMeshBus` (UDP unicast + multicast discovery)
- Add `core/mesh.py:527` — `start_discovery()` enables UDP multicast peer discovery.

---

## Requirement 3: Decentralized decision-making

**Verified Status:** PASS

### Evidence Accuracy

| Claimed Evidence | Line | Verdict |
|---|---|---|
| `core/consensus.py:47` — `DeterministicResolver` | 47 | Correct |
| `core/consensus.py:234` — `resolve_claims()` runs BFT auction | 234 | Correct |
| `core/consensus.py:302` — quorum = `len(peer_ids) // 2 + 1` | 302 | Correct |
| `core/consensus.py:175` — `_majority_choice()` picks winner | 175 | Correct |
| `core/consensus.py:188` — `_collect_quorum_votes()` gathers mesh votes with 500ms timeout | 188 | Correct. Default `quorum_timeout_s=0.5`. |

### Tests

| Claimed Test | Line | Verdict |
|---|---|---|
| `tests/test_consensus.py:73` — consensus collects real votes over mesh | 73 | Correct |
| `tests/test_consensus.py:345` — concurrent claims resolved deterministically | 345 | Correct |
| `tests/test_stress.py:94` — 5 drones claim same cell, BFT resolves | 94 | Correct |

### Recommended Corrections
- None. This requirement is the cleanest in the document.

---

## Requirement 4: Fault tolerance / failure recovery

**Verified Status:** PASS

### Evidence Accuracy

| Claimed Evidence | Line | Verdict | Notes |
|---|---|---|---|
| `failure/network_injector.py:16` — `NetworkInjector` simulates packet loss (0-100%) | 16 | Correct | `class NetworkInjector(MeshBusProtocol):` with `packet_loss` clamped to 0.0-1.0. |
| `core/heartbeat.py:33` — `is_stale()` detects dead peers by timeout | 33 | Correct | `def is_stale(...)` exists. |
| `simulation/stub.py:542` — stale heartbeat triggers zone release | 542 | Correct | Log line in `_mark_drone_stale()`. |
| `simulation/stub.py:786` — `_check_recovery()` re-admits peers that resume heartbeating | 786 | **MISLEADING** | `_check_recovery()` does **not** re-admit peers based on heartbeating. It performs a **timed revive** of the specifically configured `fail_drone` after `fail_at + 20` seconds (line 793). There is no heartbeat resumption check. |
| `main.py:68` — CLI `--packet-loss` and `--fail` flags | 68 | Correct | `parser.add_argument("--packet-loss", ...)` exists. |

### Tests

| Claimed Test | Line | Verdict |
|---|---|---|
| `tests/test_stress.py:82` — 50% packet loss, BFT still resolves | 82 | Correct |
| `tests/test_integration.py:107` — peer crash recovery | 107 | Correct. `TestPeerCrashRecovery` class. |
| `tests/test_profile.py:195` — 10-node cluster with 2 nodes down, 8+ survive | 195 | Correct |
| `tests/test_simulation.py:11` — end-to-end with failure and survivor | 11 | Correct |

### Recommended Corrections
- Change `simulation/stub.py:786` description to: `_check_recovery()` performs timed revival of the configured failed drone after 20s (line 786-803).
- Or replace with: `simulation/runtime.py:374` — `_attempt_reconnect()` rejoins degraded peer to mesh when backoff expires.

---

## Requirement 5: Scalability (10+ agents)

**Verified Status:** PASS

### Evidence Accuracy

| Claimed Evidence | Line | Verdict | Notes |
|---|---|---|---|
| `tests/test_stress.py:34` — `test_max_drones_10_grid_10` | 34 | Correct | 10 drones, 10×10 grid. |
| `tests/test_break.py:585` — `test_100_drones_20x20_grid_no_crash` | 585 | Correct | 100 drones, 20×20 grid. |
| `tests/test_profile.py:24` — parametric CPU/RAM test up to 50 drones | 24 | Correct | Parametrized for 5/8, 10/12, 20/16, 50/20. |
| `tests/test_stress.py:153` — 1000 publishes under 1 second | 153 | **MISLEADING** | This tests **mesh bus throughput**, not agent scalability. It does not validate 10+ agents coordinating. |

### Tests

| Claimed Test | Line | Verdict |
|---|---|---|
| `tests/test_stress.py` (full file) | — | Correct, contains multi-drone tests. |
| `tests/test_profile.py:24` — drone/grid combos | 24 | Correct |

### Recommended Corrections
- Replace `tests/test_stress.py:153` with a scalability-relevant test, e.g.:
  - `tests/test_stress.py:34` — `test_max_drones_10_grid_10` (already listed, but could add `test_100_drones_20x20_grid_no_crash` here too)
  - `tests/test_profile.py:24` — parametric scale test up to 50 drones
- **Overstated claim in Notes:** "100 drones initialize and complete without crash" — the test runs for only **3 seconds** (`duration=3, tick_seconds=1`), so it's 3 ticks. "Complete" implies mission duration. Change to: "100 drones initialize and survive 3 ticks without crash; tick latency not benchmarked at this scale."

---

## Requirement 6: Real-time operation

**Verified Status:** PARTIAL (confirmed)

### Evidence Accuracy

| Claimed Evidence | Line | Verdict | Notes |
|---|---|---|---|
| `dashboard/tui.py` — live terminal UI polls runtime state every tick | — | **MISLEADING** | `TUIDashboard` is a **render-only** class. It does not poll; `main.py` calls `simulation.get_state()` and `dashboard.build_frame()` on a sleep loop. The TUI itself has no polling mechanism. |
| `scripts/serve_live_runtime.py` — HTTP SSE telemetry stream | — | Correct | `_handle_sse_stream()` serves SSE at `/stream`. |
| `core/consensus.py:49` — `quorum_timeout_s = 0.5` | 49 | Correct | Default timeout in `DeterministicResolver.__init__`. |
| `tests/test_profile.py:52` — documents 500ms consensus timeout blocking simulation tick | 52 | Correct | `test_consensus_timeout_cost` measures and documents this. |
| `tests/test_profile.py:166` — "1 contested claim blocks for ~500ms" | 166 | Correct | Test prints this GAP message. |

### Tests

| Claimed Test | Line | Verdict |
|---|---|---|
| `tests/test_profile.py:52` — `test_consensus_timeout_cost` | 52 | Correct |
| `tests/test_stress.py:153` — mesh bus performance under 1s | 153 | Weak relevance. Bus throughput != real-time coordination. |

### Recommended Corrections
- Change `dashboard/tui.py` evidence to: `main.py:167-176` — CLI loop calls `get_state()` and renders TUI every tick with `time.sleep(dashboard.tick_delay_seconds)`.
- **Notes claim:** "async Rust bridge providing deterministic heartbeat and peer TTL tracking" and "sub-millisecond heartbeat relay" — **no test or benchmark substantiates the sub-millisecond claim**. The Rust bridge (`core/bridge.py` / `VertexMeshBus`) has no performance tests at all. Remove or qualify: "Async Rust bridge is used for Vertex transport; performance not independently benchmarked."

---

## Requirement 7: Deterministic behavior

**Verified Status:** PASS

### Evidence Accuracy

| Claimed Evidence | Line | Verdict |
|---|---|---|
| `core/consensus.py:47` — `DeterministicResolver` | 47 | Correct |
| `tests/test_consensus.py:54` — deterministic repeated contention | 54 | Correct |
| `tests/test_stress.py:142` — identical seeds yield identical results | 142 | Correct |
| `simulation/proof.py:112-114` — `swarm_id` is SHA256 of sorted audit trail | 112-114 | Correct |

### Tests

| Claimed Test | Line | Verdict |
|---|---|---|
| `tests/test_consensus.py:54` | 54 | Correct |
| `tests/test_stress.py:142` | 142 | Correct |
| `tests/test_proof.py:316` — swarm_id deterministic for same events | 316 | Correct |

### Recommended Corrections
- **Notes claim:** "No stochastic hidden state" — **FALSE**. `failure/network_injector.py:13` creates `_rng = random.Random()` with **no seed**. When `packet_loss > 0` is used without explicitly seeding the network injector, runs are non-deterministic. The determinism tests all use `packet_loss=0.0` or don't check cross-run equality with loss. 
- Correct to: "Determinism is guaranteed by seeded RNG and deterministic auction logic **when packet loss is disabled or the network injector is seeded**."

---

## Requirement 8: Cryptographic proof / audit trail

**Verified Status:** PASS

### Evidence Accuracy

| Claimed Evidence | Line | Verdict | Notes |
|---|---|---|---|
| `core/mesh.py:102-122` — `sign_envelope()` and `verify_envelope()` use HMAC-SHA256 | 102-122 | Correct | `sign_envelope` and `verify_envelope` functions use `_hmac.new(..., _hashlib.sha256)`. |
| `core/mesh.py:911` — FoxMQMeshBus verifies HMAC on incoming | 911 | Correct | `if not verify_envelope(envelope):` drops invalid messages. |
| `core/mesh.py:963` — FoxMQMeshBus signs outgoing envelopes | 963 | Correct | `encode_envelope(sign_envelope(envelope))`. |
| `simulation/proof.py:16` — `ProofLogger` writes every event to `proofs.jsonl` | 16 | Correct | `class ProofLogger:` — events are written via `_write_line()`. |
| `simulation/proof.py:205-223` — `compute_peer_signatures()` builds SHA256 per-peer audit hashes | 205-223 | Correct | `def compute_peer_signatures(...)` exists. |
| `scripts/verify_poc.py:13-42` — standalone verifier script | 13-42 | Correct | `verify()` function checks fields and signatures. |

### Tests

| Claimed Test | Line | Verdict |
|---|---|---|
| `tests/test_mesh_signing.py:3-27` — sign/verify round trip | 3-27 | Correct |
| `tests/test_break.py:165-209` — tamper detection and replay resistance | 165-209 | Correct. `TestHMACSigningContracts`. |
| `tests/test_proof.py:296` — signatures reproducible from audit trail | 296 | Correct |

### Recommended Corrections
- Minor: `verify_envelope()` returns `True` when `_MESH_SECRET` is empty (line 116-117), effectively disabling verification. The document should note this: "HMAC verification is skipped if `ENTROPYHUNT_MESH_SECRET` is unset."

---

## Requirement 9: Search & Rescue relevance

**Verified Status:** PASS

### Evidence Accuracy

| Claimed Evidence | Line | Verdict |
|---|---|---|
| `MISSION.md:11-16` — SAR scenario | 11-16 | Correct |
| `core/certainty.py:53` — `shannon_entropy()` drives search priority | 53 | Correct |
| `core/selector.py:39` — `select_next_zone()` picks highest-entropy unsearched cell | 39 | Correct |
| `auction/voronoi.py:23` — `ownership_grid()` partitions terrain into drone zones | 23 | Correct |
| `simulation/stub.py:698` — `survivor_found` event emitted when certainty > 0.92 | ~698 | Correct (event emitted at lines 696-709; threshold is `completion_certainty` default 0.92) |
| `docs/screenshots/survivor-found.png` | — | **File exists** |

### Tests

| Claimed Test | Line | Verdict |
|---|---|---|
| `tests/test_selector.py:8` — highest entropy cell selection | 8 | Correct |
| `tests/test_simulation.py:11` — end-to-end survivor found | 11 | Correct |
| `tests/test_break.py:68` — Shannon entropy boundaries | 68 | Correct |

### Recommended Corrections
- None. This requirement is fully substantiated.

---

## Requirement 10: Demo / reproducibility

**Verified Status:** PASS

### Evidence Accuracy

| Claimed Evidence | Line | Verdict |
|---|---|---|
| `setup.sh` — installs deps and creates `.env` | — | Correct |
| `scripts/run_demo.sh` — single-script demo | — | Correct |
| `main.py:33-72` — CLI with flags | 33-72 | Correct |
| `pytest --collect-only` — 899 tests | — | **INACCURATE** |
| `scripts/verify_poc.py` — validates PoC | — | Correct |

### Tests

| Claimed Test | Line | Verdict |
|---|---|---|
| `tests/` (899 cases total) | — | **Wrong count** |
| `tests/test_stress.py:142` — seed-based reproducibility | 142 | Correct |
| `tests/test_simulation.py` — end-to-end deterministic runs | — | Correct |

### Recommended Corrections
- **Test count:** `pytest --collect-only` reports **903 tests**, not 899. Update the count throughout the document (lines 9 and 123).
- One-line verifier table at line 137 references `test_consensus_blocks_on_contention` but the actual test name is `test_consensus_blocks_on_contention` — wait, let me check... Actually at line 137 it says `test_consensus_blocks_on_contention` but looking at test_profile.py line 165, the test is `test_consensus_blocks_on_contention`. That matches. (I already verified this earlier.)

---

## Critical Issues (Must Fix Before Submission)

1. **Requirement 2 — `VertexMeshBus` mislabeled as UDP multicast P2P.** This is a category error. Judges reading the evidence will look at `VertexMeshBus` and find a Rust bridge, not UDP multicast. Replace with `LocalPeerMeshBus` for UDP evidence.

2. **Requirement 1 — `PeerRuntime` wrong line number.** Line 39 is a constant, not the class.

3. **Requirement 4 — `_check_recovery()` mischaracterized.** It does not recover based on heartbeats. It is a hardcoded timed revive.

4. **Requirement 7 — "No stochastic hidden state" is false.** The `NetworkInjector` uses an unseeded global RNG.

5. **Test count:** 903, not 899.

## Honest Limitations Section

The "Honest Limitations" section (lines 145-152) is **accurate and well-written**. All five limitations are backed by explicit GAP tests in `tests/test_profile.py`. No corrections needed.

---

*End of audit.*
