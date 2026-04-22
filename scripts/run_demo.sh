#!/usr/bin/env bash
# Entropy Hunt — Track 2 Demo
# Auto-detects FoxMQ; falls back to UDP peer transport.
set -e
cd "$(dirname "$0")/.."

echo '=== Entropy Hunt: Track 2 Search & Rescue Swarms ==='
echo ''

TRANSPORT_ARGS=""
FOXMQ_PID=""

if command -v foxmq &>/dev/null; then
  echo "FoxMQ detected — starting broker on port 1884..."
  foxmq run --allow-anonymous-login \
    --secret-key-file=foxmq.d/key_0.pem \
    --mqtt-addr=127.0.0.1:1884 \
    --cluster-addr=127.0.0.1:19793 \
    foxmq.d &
  FOXMQ_PID=$!
  trap "kill $FOXMQ_PID 2>/dev/null || true" EXIT
  sleep 1
  TRANSPORT_ARGS="--transport foxmq --mqtt-port 1884"
  echo "Transport: FoxMQ (MQTT port 1884)"
else
  echo "foxmq not found — using in-process mesh bus"
  TRANSPORT_ARGS=""
  echo "Transport: in-process (InMemoryMeshBus)"
fi

echo ''
echo '1. Running swarm simulation (5 drones, 60s, 20% packet loss, 1 node failure)...'
python3 main.py \
  --mode stub \
  --drones 5 \
  --grid 8 \
  --duration 60 \
  --tick-seconds 1 \
  --target 5,3 \
  --fail drone_2 \
  --fail-at 5 \
  --packet-loss 0.2 \
  --stop-on-survivor \
  --proofs proofs.jsonl \
  --final-map final_map.json \
  $TRANSPORT_ARGS

echo ''
echo '2. Verifying Proof of Coordination...'
python3 scripts/verify_poc.py

echo ''
echo '3. Summary:'
python3 -c "
import json
poc = json.load(open('proof_of_coordination.json'))
print(f\"  Transport     : {poc['mesh_transport']}\")
print(f\"  Swarm ID      : {poc['swarm_id']}\")
print(f\"  BFT rounds    : {poc['bft_rounds_total']}\")
print(f\"  Nodes dropped : {poc.get('nodes_that_dropped', [])}\")
print(f\"  Packet loss   : {poc['packet_loss_survived']}\")
print(f\"  Survivor found: {poc['survivor_found']}\")
print(f\"  Coverage      : {poc.get('grid_coverage_pct')}\")
print(f\"  Peers         : {list(poc['peer_audit_hashes'].keys())}\")
"
echo ''
echo 'Demo complete. proof_of_coordination.json written.'
