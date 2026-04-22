#!/usr/bin/env bash
# Entropy Hunt — Demo Smoke Test
# Usage: ./scripts/demo_smoke.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

info() { printf '\033[1;34m[INFO]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[OK]\033[0m   %s\n' "$*"; }
err()  { printf '\033[1;31m[FAIL]\033[0m %s\n' "$*" >&2; }

info "Running demo smoke test..."

# Run demo with a 5-second simulation, capped at 15 seconds total
OUT_FILE="/tmp/demo_smoke_$$.out"
ERR_FILE="/tmp/demo_smoke_$$.err"

EXIT_CODE=0
timeout 15 ./demo.sh --no-interactive --duration 5 --drones 3 --grid 5 >"${OUT_FILE}" 2>"${ERR_FILE}" || EXIT_CODE=$?

# Assert exit code 0
if [[ ${EXIT_CODE} -ne 0 ]]; then
    err "Demo exited with code ${EXIT_CODE} (expected 0)"
    echo "--- stdout ---"
    cat "${OUT_FILE}"
    echo "--- stderr ---"
    cat "${ERR_FILE}"
    rm -f "${OUT_FILE}" "${ERR_FILE}"
    exit 1
fi

# Assert stdout contains "Demo complete" or "Complete"
if ! grep -qiE "Demo complete|Complete" "${OUT_FILE}"; then
    err "stdout missing 'Demo complete' or 'Complete'"
    echo "--- stdout ---"
    cat "${OUT_FILE}"
    rm -f "${OUT_FILE}" "${ERR_FILE}"
    exit 1
fi

# Assert stderr contains no "ERROR" or "FAIL"
if grep -qiE "ERROR|FAIL" "${ERR_FILE}"; then
    err "stderr contained ERROR or FAIL"
    echo "--- stderr ---"
    cat "${ERR_FILE}"
    rm -f "${OUT_FILE}" "${ERR_FILE}"
    exit 1
fi

rm -f "${OUT_FILE}" "${ERR_FILE}"

ok "Smoke test passed"
exit 0
