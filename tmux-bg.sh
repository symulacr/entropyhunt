#!/bin/bash
set -euo pipefail

SESSION="entropyhunt-bg"
REPO="/home/ubuntu/entropyhunt"

cd "$REPO"

if tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux kill-session -t "$SESSION"
    sleep 0.5
fi

mkdir -p peer-runs

tmux new-session -d -s "$SESSION" -n demo
tmux split-window -h -t "$SESSION:0"

tmux send-keys -t "$SESSION:0.0" \
    "cd $REPO && ./demo.sh --no-interactive --duration 600 2>&1 | tee /tmp/entropyhunt_sim.log" \
    C-m

tmux send-keys -t "$SESSION:0.1" \
    "cd $REPO && python3 scripts/serve_live_runtime.py --port 8765 --snapshot-dir peer-runs > /tmp/entropyhunt_server.log 2>&1 &" \
    C-m

tmux send-keys -t "$SESSION:0.1" \
    "sleep 2 && curl -s http://127.0.0.1:8765/snapshot.json > /dev/null && echo 'Server OK' || echo 'Server starting...'" \
    C-m

tmux send-keys -t "$SESSION:0.1" \
    "cd $REPO && bun dashboard/tui_monitor.ts --source http://127.0.0.1:8765/snapshot.json" \
    C-m

tmux resize-pane -t "$SESSION:0.0" -x 45%

echo "Tmux session '$SESSION' started."
echo "Attach: tmux attach -t $SESSION"
echo "Kill:   tmux kill-session -t $SESSION"
