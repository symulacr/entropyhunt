#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8895}"
COUNT="${COUNT:-2}"
DURATION="${DURATION:-120}"
GRID="${GRID:-10}"
TARGET="${TARGET:-7,3}"
LOG_PATH="${LOG_PATH:-/tmp/entropyhunt_ros_control_smoke.log}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'error: missing required command: %s\n' "$1" >&2
    exit 1
  }
}

need_cmd bun
need_cmd docker
need_cmd python3

cleanup() {
  if [[ -n "${RUN_PID:-}" ]] && kill -0 "${RUN_PID}" >/dev/null 2>&1; then
    kill "${RUN_PID}" >/dev/null 2>&1 || true
    wait "${RUN_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

printf '==> launching ROS Docker runtime control smoke on port %s\n' "${PORT}"
cd "${ROOT_DIR}"
bun --silent runtime/run.ts \
  --mode ros2 \
  --ros-runtime docker \
  --count "${COUNT}" \
  --duration "${DURATION}" \
  --grid "${GRID}" \
  --target "${TARGET}" \
  --no-monitor \
  --show-launcher \
  --ros-snapshot-port "${PORT}" >"${LOG_PATH}" 2>&1 &
RUN_PID=$!

wait_for_json() {
  local url="$1"
  local attempts="${2:-120}"
  local delay="${3:-1}"
  python3 - "$url" "$attempts" "$delay" <<'PY'
import json, sys, time, urllib.request
url = sys.argv[1]
attempts = int(sys.argv[2])
delay = float(sys.argv[3])
for _ in range(attempts):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            data = json.load(response)
        print(json.dumps(data))
        raise SystemExit(0)
    except Exception:
        time.sleep(delay)
raise SystemExit(1)
PY
}

SNAPSHOT_URL="http://127.0.0.1:${PORT}/snapshot.json"
CONTROL_URL="http://127.0.0.1:${PORT}/control"

printf '==> waiting for snapshot endpoint\n'
SNAPSHOT_JSON="$(wait_for_json "${SNAPSHOT_URL}")" || {
  printf 'error: snapshot endpoint never became ready\n' >&2
  tail -n 120 "${LOG_PATH}" >&2 || true
  exit 1
}
python3 - "${SNAPSHOT_JSON}" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
print(json.dumps({
    "tick_seconds": data["config"].get("tick_seconds"),
    "requested_drone_count": data["config"].get("requested_drone_count"),
    "control_capabilities": data["config"].get("control_capabilities"),
}, indent=2))
PY

printf '\n==> checking control endpoint\n'
CONTROL_JSON="$(wait_for_json "${CONTROL_URL}")" || {
  printf 'error: control endpoint never became ready\n' >&2
  tail -n 120 "${LOG_PATH}" >&2 || true
  exit 1
}
python3 - "${CONTROL_JSON}" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
assert data["control_capabilities"]["tick_seconds"] == "live"
assert data["control_capabilities"]["requested_drone_count"] == "next_run"
print(json.dumps(data, indent=2))
PY

measure_delta() {
  local seconds="$1"
  python3 - "$SNAPSHOT_URL" "$seconds" <<'PY'
import json, sys, time, urllib.request
url = sys.argv[1]
seconds = float(sys.argv[2])
def load():
    with urllib.request.urlopen(url, timeout=3) as response:
        return json.load(response)
before = load()
before_counts = [int(drone.get("searched_cells", 0)) for drone in before.get("drones", [])]
time.sleep(seconds)
after = load()
after_counts = [int(drone.get("searched_cells", 0)) for drone in after.get("drones", [])]
deltas = [b - a for a, b in zip(before_counts, after_counts)]
print(json.dumps({
    "tick_seconds": after["config"].get("tick_seconds"),
    "requested_drone_count": after["config"].get("requested_drone_count"),
    "before": before_counts,
    "after": after_counts,
    "delta": deltas,
}, indent=2))
PY
}

post_control() {
  local payload="$1"
  python3 - "$CONTROL_URL" "$payload" <<'PY'
import json, sys, urllib.request
url = sys.argv[1]
payload = json.loads(sys.argv[2])
request = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=3) as response:
    print(response.read().decode("utf-8"))
PY
}

printf '\n==> baseline speed sample\n'
BASELINE="$(measure_delta 3.2)"
printf '%s\n' "${BASELINE}"

printf '\n==> posting slower tick_seconds=2.0 requested_drone_count=4\n'
post_control '{"tick_seconds": 2.0, "requested_drone_count": 4}'
SLOW="$(measure_delta 3.2)"
printf '%s\n' "${SLOW}"

printf '\n==> posting faster tick_seconds=0.5 requested_drone_count=5\n'
post_control '{"tick_seconds": 0.5, "requested_drone_count": 5}'
FAST="$(measure_delta 3.2)"
printf '%s\n' "${FAST}"

printf '\n==> validating observed runtime effect\n'
python3 - "${BASELINE}" "${SLOW}" "${FAST}" <<'PY'
import json, sys
baseline = json.loads(sys.argv[1])
slow = json.loads(sys.argv[2])
fast = json.loads(sys.argv[3])

baseline_max = max(baseline["delta"] or [0])
slow_max = max(slow["delta"] or [0])
fast_max = max(fast["delta"] or [0])

assert slow["tick_seconds"] == 2.0, slow
assert slow["requested_drone_count"] == 4, slow
assert fast["tick_seconds"] == 0.5, fast
assert fast["requested_drone_count"] == 5, fast
assert slow_max < baseline_max, (baseline, slow)
assert fast_max > slow_max, (slow, fast)
print(json.dumps({
    "baseline_max_delta": baseline_max,
    "slow_max_delta": slow_max,
    "fast_max_delta": fast_max,
}, indent=2))
PY

printf '\n==> log evidence\n'
grep -E "Operator control updated|runtime tick updated" "${LOG_PATH}" | tail -n 12 || true

printf '\nROS Docker control smoke passed.\n'
printf 'Log: %s\n' "${LOG_PATH}"
