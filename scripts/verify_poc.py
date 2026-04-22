#!/usr/bin/env python3
import json
import sys
from pathlib import Path

from simulation.proof import compute_peer_signatures as compute_peer_audit_hashes


def verify(path: str = "proof_of_coordination.json") -> bool:
    with Path(path).open() as f:
        poc = json.load(f)
    required = [
        "version", "swarm_id", "generated_at", "bft_rounds_total",
        "peer_audit_hashes", "audit_trail", "consensus_rounds",
        "mesh_transport", "packet_loss_survived", "survivor_found",
    ]
    missing = [f for f in required if f not in poc]
    if missing:
        print(f"FAIL: missing fields: {missing}")
        return False

    print(f'version          : {poc["version"]}')
    print(f'swarm_id         : {poc["swarm_id"]}')
    print(f'generated_at     : {poc["generated_at"]}')
    print(f'bft_rounds_total : {poc["bft_rounds_total"]}')
    print(f'nodes_dropped    : {poc.get("nodes_that_dropped", [])}')
    print(f'packet_loss      : {poc["packet_loss_survived"]}')
    print(f'survivor_found   : {poc["survivor_found"]}')
    print(f'grid_coverage    : {poc.get("grid_coverage_pct")}')
    print(f'peers            : {list(poc["peer_audit_hashes"].keys())}')
    print(f'audit_events     : {len(poc["audit_trail"])}')
    print(f'consensus_rounds : {len(poc["consensus_rounds"])}')

    computed = compute_peer_audit_hashes(poc["audit_trail"])
    sig_failures = [
        f"  {pid}: expected {expected[:16]}… got {computed.get(pid, '(missing)')[:16]}…"
        for pid, expected in poc["peer_audit_hashes"].items()
        if computed.get(pid) != expected
    ]
    if sig_failures:
        print("FAIL: signature mismatch:")
        for line in sig_failures:
            print(line)
        return False

    n = len(poc["peer_audit_hashes"])
    print(f"signatures       : OK ({n} peer{'s' if n != 1 else ''} verified)")
    print("OK: all required fields present and signatures verified")
    return True


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "proof_of_coordination.json"
    sys.exit(0 if verify(path) else 1)
