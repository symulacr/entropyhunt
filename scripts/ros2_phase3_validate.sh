#!/usr/bin/env bash
set -eo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_DIR="${ROOT_DIR}/ros2_ws"

DISTRO="${ROS_DISTRO_OVERRIDE:-${ROS_DISTRO:-humble}}"
COUNT="${COUNT:-5}"
GRID="${GRID:-10}"
TARGET_X="${TARGET_X:-7}"
TARGET_Y="${TARGET_Y:-3}"
FAIL_DRONE="${FAIL_DRONE:-drone_2}"
FAIL_AT="${FAIL_AT:-60}"
SNAPSHOT_PATH="${SNAPSHOT_PATH:-/tmp/entropyhunt_ros_snapshot.json}"
SNAPSHOT_HOST="${SNAPSHOT_HOST:-127.0.0.1}"
SNAPSHOT_PORT="${SNAPSHOT_PORT:-8776}"
LAUNCH_WAIT_SECONDS="${LAUNCH_WAIT_SECONDS:-6}"
LAUNCH_LOG="${LAUNCH_LOG:-/tmp/entropyhunt_ros_launch.log}"

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

need_cmd python3
need_cmd colcon
need_cmd ros2

[[ -d "${WORKSPACE_DIR}" ]] || die "workspace not found: ${WORKSPACE_DIR}"
[[ -f "/opt/ros/${DISTRO}/setup.bash" ]] || die "ROS distro setup not found: /opt/ros/${DISTRO}/setup.bash"

printf '==> building ROS workspace (%s)\n' "${WORKSPACE_DIR}"
cd "${WORKSPACE_DIR}"
colcon build

# shellcheck disable=SC1090
source "/opt/ros/${DISTRO}/setup.bash"
# shellcheck disable=SC1091
source "${WORKSPACE_DIR}/install/setup.bash"

printf '\n==> package discovery\n'
ros2 pkg list | grep -E '^entropy_hunt_interfaces$' >/dev/null || die "entropy_hunt_interfaces not discoverable"
ros2 pkg list | grep -E '^entropy_hunt_ros2$' >/dev/null || die "entropy_hunt_ros2 not discoverable"

printf '==> interface checks\n'
ros2 interface show entropy_hunt_interfaces/msg/DroneState >/dev/null
ros2 interface show entropy_hunt_interfaces/msg/Heartbeat >/dev/null
ros2 interface show entropy_hunt_interfaces/msg/BftRoundResult >/dev/null

printf '\n==> launching ROS swarm demo\n'
rm -f "${SNAPSHOT_PATH}"
ros2 launch entropy_hunt_ros2 demo.launch.py \
  count:="${COUNT}" \
  grid:="${GRID}" \
  target_x:="${TARGET_X}" \
  target_y:="${TARGET_Y}" \
  fail_drone:="${FAIL_DRONE}" \
  fail_at:="${FAIL_AT}" \
  snapshot_path:="${SNAPSHOT_PATH}" \
  snapshot_host:="${SNAPSHOT_HOST}" \
  snapshot_port:="${SNAPSHOT_PORT}" >"${LAUNCH_LOG}" 2>&1 &
LAUNCH_PID=$!

cleanup() {
  if kill -0 "${LAUNCH_PID}" >/dev/null 2>&1; then
    kill "${LAUNCH_PID}" >/dev/null 2>&1 || true
    wait "${LAUNCH_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

sleep "${LAUNCH_WAIT_SECONDS}"

printf '\n==> ROS graph\n'
ros2 node list || true
printf '\n'
ros2 topic list || true

printf '\n==> sample topic traffic\n'
if command -v timeout >/dev/null 2>&1; then
  timeout 3 ros2 topic echo /swarm/drone_state --once || true
  timeout 3 ros2 topic echo /swarm/claims --once || true
  timeout 3 ros2 topic echo /swarm/bft_result --once || true
else
  printf 'timeout command not found; skipping bounded topic echo checks\n'
fi

printf '\n==> snapshot artifact\n'
[[ -f "${SNAPSHOT_PATH}" ]] || die "snapshot file was not written: ${SNAPSHOT_PATH}"
python3 - <<'PY' "${SNAPSHOT_PATH}"
import json, sys
path = sys.argv[1]
data = json.load(open(path))
required = ["stats", "config", "grid", "drones", "events", "survivor_found"]
missing = [key for key in required if key not in data]
if missing:
    raise SystemExit(f"snapshot missing keys: {missing}")
print(json.dumps({
    "stats": data["stats"],
    "config": data["config"],
    "drone_count": len(data["drones"]),
    "event_count": len(data["events"]),
    "survivor_found": data["survivor_found"],
}, indent=2))
PY

if command -v curl >/dev/null 2>&1; then
  printf '\n==> snapshot HTTP check\n'
  curl -fsS "http://${SNAPSHOT_HOST}:${SNAPSHOT_PORT}/snapshot.json" | python3 - <<'PY'
import json, sys
data = json.load(sys.stdin)
print(json.dumps({
    "stats": data.get("stats", {}),
    "config": data.get("config", {}),
    "drone_count": len(data.get("drones", [])),
    "event_count": len(data.get("events", [])),
}, indent=2))
PY
fi

printf '\nValidation complete.\n'
printf 'Launch log: %s\n' "${LAUNCH_LOG}"
printf 'Snapshot file: %s\n' "${SNAPSHOT_PATH}"
printf '\nTo attach the TUI:\n'
printf '  bun run dashboard/tui_monitor_v2.ts --source http://%s:%s/snapshot.json\n' "${SNAPSHOT_HOST}" "${SNAPSHOT_PORT}"
