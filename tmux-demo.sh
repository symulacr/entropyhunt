#!/bin/bash
# Entropy Hunt — Tmux Side-by-Side Demo
# Left pane: Console simulation
# Right pane: TUI dashboard

SESSION="entropyhunt"
REPO="/home/ubuntu/entropyhunt"

# Kill existing session
tmux kill-session -t "$SESSION" 2>/dev/null

# Create new session with simulation in left pane
tmux new-session -d -s "$SESSION" "cd $REPO && ./demo.sh --no-interactive --duration 60"

# Split horizontally and run live server + TUI in right pane
tmux split-window -h -t "$SESSION" "cd $REPO && python3 scripts/serve_live_runtime.py --port 8765 --snapshot-dir peer-runs & sleep 2 && bun dashboard/tui_monitor.ts --source http://127.0.0.1:8765/snapshot.json"

# Adjust pane sizes (left 40%, right 60%)
tmux resize-pane -t "$SESSION:0.0" -x 40%

# Attach to session
tmux attach -t "$SESSION"
