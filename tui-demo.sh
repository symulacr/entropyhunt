#!/bin/bash
set -euo pipefail

REPO="/home/ubuntu/entropyhunt"
cd "$REPO"

mkdir -p peer-runs

info()  { printf '\033[1;34m[INFO]\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m[OK]\033[0m   %s\n' "$*"; }

cleanup() {
    info "Shutting down..."
    if [[ -n "${SIM_PID:-}" ]] && kill -0 "$SIM_PID" 2>/dev/null; then
        kill "$SIM_PID" 2>/dev/null || true
        wait "$SIM_PID" 2>/dev/null || true
    fi
    if [[ -n "${SERVER_PID:-}" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
    ok "Clean exit"
}

trap cleanup INT TERM EXIT

info "Starting simulation (600s)..."
./demo.sh --no-interactive --duration 600 > /tmp/entropyhunt_sim.log 2>&1 &
SIM_PID=$!
ok "Simulation PID $SIM_PID"

info "Starting live server..."
python3 scripts/serve_live_runtime.py --port 8765 --snapshot-dir peer-runs > /tmp/entropyhunt_server.log 2>&1 &
SERVER_PID=$!
ok "Server PID $SERVER_PID"

info "Waiting for server..."
for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:8765/snapshot.json > /dev/null 2>&1; then
        ok "Server ready"
        break
    fi
    sleep 1
done

info "Launching TUI..."
bun dashboard/tui_monitor.ts --source http://127.0.0.1:8765/snapshot.json

exit 0
