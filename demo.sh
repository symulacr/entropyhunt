#!/usr/bin/env bash
# Entropy Hunt — Live Swarm Demo (full-stack)
# Usage: ./demo.sh [OPTIONS]
# Design inspired by ckm:banner-design principles:
#   - Neon/Cyberpunk: glowing ANSI 256 gradients on dark terminal canvas
#   - Geometric: heavy Unicode box-drawing frames & glyph composition
#   - Bold Typography: strong hierarchy, max 2 type weights, centered safe-zone
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"

cd "${REPO_ROOT}"

DRONES=5
GRID=8
DURATION=60
PACKET_LOSS=0.1
USE_TUI=false
NO_INTERACTIVE=false

readonly C_NEON_CYAN=$'\033[38;5;51m'
readonly C_CYAN=$'\033[38;5;81m'
readonly C_BLUE=$'\033[38;5;39m'
readonly C_DEEP_BLUE=$'\033[38;5;33m'
readonly C_AMBER=$'\033[38;5;214m'
readonly C_GREEN=$'\033[1;38;5;82m'
readonly C_LIME=$'\033[38;5;118m'
readonly C_RED=$'\033[1;38;5;196m'
readonly C_MAGENTA=$'\033[38;5;201m'
readonly C_WHITE=$'\033[1;38;5;255m'
readonly C_DIM=$'\033[2;38;5;240m'
readonly C_RESET=$'\033[0m'
readonly C_BOLD=$'\033[1m'

INTERACTIVE=false

_timestamp() {
    date '+%H:%M:%S'
}

typewrite() {
    local text="$1"
    local delay="${2:-0.01}"
    if [[ "${INTERACTIVE}" != true ]]; then
        printf '%s' "${text}"
        return
    fi
    local i
    for ((i = 0; i < ${#text}; i++)); do
        printf '%s' "${text:$i:1}"
        sleep "${delay}"
    done
}

spinner() {
    local msg="$1"
    local -a frames=('◐' '◓' '◑' '◒')
    if [[ "${INTERACTIVE}" != true ]]; then
        return
    fi
    printf '\033[?25l'
    local i=0
    while true; do
        printf '\r  %s %s %s' "${C_CYAN}${frames[i]}${C_RESET}" "${C_DIM}${msg}${C_RESET}" "${C_RESET}"
        sleep 0.08
        i=$(((i + 1) % 4))
    done
}

stop_spinner() {
    local pid="${1:-}"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
        kill "${pid}" >/dev/null 2>&1 || true
        wait "${pid}" >/dev/null 2>&1 || true
    fi
    printf '\r\033[K\033[?25h'
}

progress_bar() {
    local current="$1"
    local total="$2"
    local label="${3:-}"
    local width=30
    if [[ "${total}" -le 0 ]]; then
        total=1
    fi
    local filled=$((width * current / total))
    local empty=$((width - filled))
    local pct=$((100 * current / total))
    local bar
    bar="$(printf '%*s' "${filled}" '' | tr ' ' '█')"
    bar="${bar}$(printf '%*s' "${empty}" '' | tr ' ' '░')"
    printf '\r  %s[%s]%s %s%3d%%%s %s\n' \
        "${C_DEEP_BLUE}" "${bar}" "${C_RESET}" \
        "${C_LIME}" "${pct}" "${C_RESET}" \
        "${C_DIM}${label}${C_RESET}"
}

section_header() {
    local title="$1"
    local width=62
    local pad=$((width - ${#title}))
    local left=$((pad / 2))
    local right=$((pad - left))
    printf '\n'
    printf '  %s┏%s┓%s\n' "${C_DEEP_BLUE}" "$(printf '%*s' "${width}" '' | tr ' ' '━')" "${C_RESET}"
    printf '  %s┃%s%*s%s%s%*s%s┃%s\n' \
        "${C_DEEP_BLUE}" "${C_RESET}" \
        "${left}" '' "${C_BOLD}${C_WHITE}${title}${C_RESET}" \
        "${right}" '' \
        "${C_DEEP_BLUE}" "${C_RESET}"
    printf '  %s┣%s┫%s\n' "${C_DEEP_BLUE}" "$(printf '%*s' "${width}" '' | tr ' ' '━')" "${C_RESET}"
}

countdown() {
    local n="${1:-3}"
    if [[ "${INTERACTIVE}" != true ]]; then
        return
    fi
    local i
    for ((i = n; i > 0; i--)); do
        printf '\r  %s[%s] %sLaunching in %d...%s' \
            "${C_DEEP_BLUE}" "$(printf '%*s' "30" '' | tr ' ' '░')" \
            "${C_AMBER}" "${i}" "${C_RESET}"
        sleep 1
    done
    printf '\r  %s[%s] %sLAUNCH SEQUENCE INITIATED%s\n' \
        "${C_DEEP_BLUE}" "$(printf '%*s' "30" '' | tr ' ' '█')" \
        "${C_GREEN}" "${C_RESET}"
}

press_any_key() {
    local msg="${1:-Press any key to continue...}"
    if [[ "${INTERACTIVE}" != true ]]; then
        return
    fi
    if [[ ! -t 0 ]]; then
        return
    fi
    typewrite "  ${msg}" 0.015
    read -r -n 1 -s || true
    printf '\n'
}

info() {
    printf '%s[%s]%s %s[INFO]%s  %s\n' \
        "${C_DIM}" "$(_timestamp)" "${C_RESET}" \
        "${C_CYAN}" "${C_RESET}" "$*"
}

ok() {
    printf '%s[%s]%s %s[OK]%s    %s\n' \
        "${C_DIM}" "$(_timestamp)" "${C_RESET}" \
        "${C_GREEN}" "${C_RESET}" "$*"
}

warn() {
    printf '%s[%s]%s %s[WARN]%s  %s\n' \
        "${C_DIM}" "$(_timestamp)" "${C_RESET}" \
        "${C_AMBER}" "${C_RESET}" "$*"
}

err() {
    printf '%s[%s]%s %s[ERR]%s   %s\n' \
        "${C_DIM}" "$(_timestamp)" "${C_RESET}" \
        "${C_RED}" "${C_RESET}" "$*" >&2
}

print_banner() {
    local bc="${C_DEEP_BLUE}"
    local c1="${C_NEON_CYAN}"
    local c2="${C_CYAN}"
    local c3="${C_BLUE}"
    local am="${C_AMBER}"
    local gr="${C_GREEN}"
    local dm="${C_DIM}"
    local rs="${C_RESET}"
    local bd="${C_BOLD}"

    local p1 p2 p3 p4
    p1="  DRONE COUNT       ${gr}${DRONES}${rs}"
    p1="${p1}$(printf '%*s' $((62 - 20 - ${#DRONES})) '')"

    p2="  GRID SIZE         ${gr}${GRID}×${GRID}${rs}"
    p2="${p2}$(printf '%*s' $((62 - 19 - ${#GRID} - 1 - ${#GRID})) '')"

    local dur_str="${DURATION}s"
    p3="  MISSION DURATION  ${gr}${dur_str}${rs}"
    p3="${p3}$(printf '%*s' $((62 - 20 - ${#dur_str})) '')"

    local pl_str="${PACKET_LOSS}"
    p4="  PACKET LOSS       ${gr}${pl_str}${rs}"
    p4="${p4}$(printf '%*s' $((62 - 20 - ${#pl_str})) '')"

    printf '\n'
    printf '  %s┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓%s\n' "${bc}" "${rs}"
    printf '  %s┃%s                                                              %s┃%s\n' "${bc}" "${rs}" "${bc}" "${rs}"
    printf '  %s┃%s    %s◢◣%s  %sENTROPY HUNT%s  //  %sSWARM COORDINATION DEMO%s  %s◢◣%s    %s┃%s\n' \
        "${bc}" "${rs}" "${c1}" "${rs}" "${bd}${c2}" "${rs}" "${bd}${c3}" "${rs}" "${c1}" "${rs}" "${bc}" "${rs}"
    printf '  %s┃%s                                                              %s┃%s\n' "${bc}" "${rs}" "${bc}" "${rs}"
    printf '  %s┃%s        %sVertex Swarm Challenge 2026 · Track 2 · Search & Rescue%s        %s┃%s\n' \
        "${bc}" "${rs}" "${dm}${am}" "${rs}" "${bc}" "${rs}"
    printf '  %s┃%s                                                              %s┃%s\n' "${bc}" "${rs}" "${bc}" "${rs}"
    printf '  %s┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫%s\n' "${bc}" "${rs}"
    printf '  %s┃%s  %sDEPLOYMENT PARAMETERS%s                                       %s┃%s\n' \
        "${bc}" "${rs}" "${bd}${c3}" "${rs}" "${bc}" "${rs}"
    printf '  %s┃%s  %s─────────────────────%s                                       %s┃%s\n' \
        "${bc}" "${rs}" "${dm}" "${rs}" "${bc}" "${rs}"
    printf '  %s┃%s%s%s┃%s\n' "${bc}" "${rs}" "${p1}" "${bc}" "${rs}"
    printf '  %s┃%s%s%s┃%s\n' "${bc}" "${rs}" "${p2}" "${bc}" "${rs}"
    printf '  %s┃%s%s%s┃%s\n' "${bc}" "${rs}" "${p3}" "${bc}" "${rs}"
    printf '  %s┃%s%s%s┃%s\n' "${bc}" "${rs}" "${p4}" "${bc}" "${rs}"
    printf '  %s┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛%s\n' "${bc}" "${rs}"
    printf '\n'
}

# ── Help ─────────────────────────────────────────────────────────────────────

print_help() {
    cat <<'EOF'
Entropy Hunt — Live Swarm Demo

Usage: ./demo.sh [OPTIONS]

Options:
  --duration SECONDS   Simulation duration (default: 60)
  --drones COUNT       Number of drones (default: 5)
  --grid SIZE          Grid size (default: 8)
  --tui                Launch TUI dashboard in background
  --no-interactive     Skip all prompts/spinners (for CI)
  --help               Show this help message and exit

Description:
  Runs a live swarm simulation with the Rust vertex-node mesh bridge
  and optional TUI dashboard.

Example:
  ./demo.sh --duration 5 --drones 3 --grid 5
  ./demo.sh --tui
  ./demo.sh --no-interactive --duration 10

Requirements:
  • Run ./setup.sh first to install dependencies
  • Python 3.10+ with the entropy-hunt package installed
  • Rust/Cargo (to build vertex-node on first run)
  • Bun (optional — required for TUI dashboard)
EOF
}

require_command() {
    local cmd="$1"
    local purpose="${2:-$1}"
    if ! command -v "${cmd}" &>/dev/null; then
        err "Missing required command: ${purpose} (${cmd})"
        return 1
    fi
}

check_item() {
    local label="$1"
    local cmd="$2"
    local required="${3:-false}"
    if command -v "${cmd}" &>/dev/null; then
        printf '  %s[✓]%s %s\n' "${C_GREEN}" "${C_RESET}" "${label}"
        return 0
    else
        if [[ "${required}" == true ]]; then
            printf '  %s[✗]%s %s %s(required)%s\n' "${C_RED}" "${C_RESET}" "${label}" "${C_DIM}" "${C_RESET}"
            return 1
        else
            printf '  %s[−]%s %s %s(optional)%s\n' "${C_AMBER}" "${C_RESET}" "${label}" "${C_DIM}" "${C_RESET}"
            return 0
        fi
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --drones)
            DRONES="$2"
            shift 2
            ;;
        --grid)
            GRID="$2"
            shift 2
            ;;
        --tui)
            USE_TUI=true
            shift
            ;;
        --no-interactive)
            NO_INTERACTIVE=true
            shift
            ;;
        --help)
            print_help
            exit 0
            ;;
        *)
            err "Unknown argument: $1"
            print_help
            exit 1
            ;;
    esac
done

if [[ "${NO_INTERACTIVE}" == true ]] || [[ ! -t 1 ]]; then
    INTERACTIVE=false
else
    INTERACTIVE=true
fi

require_command python3 "Python 3"

if ! python3 -c "import main" 2>/dev/null; then
    warn "Python package 'entropy-hunt' does not appear to be installed."
    info "Run ./setup.sh first, then try again."
    exit 1
fi

if [[ "${INTERACTIVE}" == true ]]; then
    printf '\033[2J\033[H'
    typewrite ">>> ESTABLISHING SECURE UPLINK... <<<" 0.03
    printf '\n\n'
    sleep 0.2
fi

print_banner

section_header "SYSTEM CHECK"
sys_ok=true
check_item "Python 3.10+" "python3" true || sys_ok=false
check_item "Rust / Cargo" "cargo" false || true
check_item "Bun runtime" "bun" false || true

if [[ "${sys_ok}" == false ]]; then
    err "Critical dependency missing — aborting mission"
    exit 1
fi

if [[ "${INTERACTIVE}" == true ]]; then
    printf '\n'
    press_any_key "Press ENTER to initialize swarm..."
    printf '\n'
    countdown 3
    printf '\n'
else
    info "Non-interactive mode — proceeding automatically"
fi

if [[ -z "${ENTROPYHUNT_MESH_SECRET:-}" ]]; then
    info "ENTROPYHUNT_MESH_SECRET not set — using test secret for demo"
    export ENTROPYHUNT_MESH_SECRET="demo-secret-not-for-production"
fi

BG_PIDS=()
VERTEX_FIFO=""
_CLEANUP_RAN=false

cleanup() {
    if [[ "${_CLEANUP_RAN}" == true ]]; then
        return
    fi
    _CLEANUP_RAN=true
    printf '\033[?25h' >/dev/tty 2>/dev/null || true
    if [[ ${#BG_PIDS[@]} -gt 0 ]]; then
        info "Cleaning up background processes..."
        local pid
        for pid in "${BG_PIDS[@]}"; do
            kill "${pid}" 2>/dev/null || true
        done
        sleep 0.5
        for pid in "${BG_PIDS[@]}"; do
            kill -9 "${pid}" 2>/dev/null || true
        done
    fi
    if [[ -n "${VERTEX_FIFO:-}" ]] && [[ -e "${VERTEX_FIFO}" ]]; then
        exec 3>&- 2>/dev/null || true
        rm -f "${VERTEX_FIFO}"
    fi
}

trap cleanup INT TERM EXIT

VERTEX_NODE_BIN="${REPO_ROOT}/vertex-node/target/release/vertex-node"

section_header "BUILD VERTEX-NODE"

if [[ ! -f "${VERTEX_NODE_BIN}" ]]; then
    require_command cargo "Rust Cargo"
    if [[ "${INTERACTIVE}" == true ]]; then
        spinner "Compiling Rust mesh bridge..." &
        local spin_pid=$!
        local build_ok=true
        cd "${REPO_ROOT}/vertex-node"
        cargo build --release >/dev/null 2>&1 || build_ok=false
        cd "${REPO_ROOT}"
        stop_spinner "${spin_pid}"
        if [[ "${build_ok}" == false ]]; then
            err "vertex-node build failed"
            exit 1
        fi
        progress_bar 1 4 "Build complete"
    else
        info "Building vertex-node..."
        cd "${REPO_ROOT}/vertex-node"
        cargo build --release
        cd "${REPO_ROOT}"
    fi
    ok "vertex-node built"
else
    ok "vertex-node binary found"
    if [[ "${INTERACTIVE}" == true ]]; then
        progress_bar 1 4 "Build cached"
    fi
fi

export ENTROPYHUNT_VERTEX_HELPER="${VERTEX_NODE_BIN}"

section_header "MESH BRIDGE"

info "Starting mesh bridge..."
VERTEX_FIFO="/tmp/entropyhunt_vertex_$$.fifo"
rm -f "${VERTEX_FIFO}"
mkfifo "${VERTEX_FIFO}"
"${VERTEX_NODE_BIN}" --port 9000 < "${VERTEX_FIFO}" >/dev/null 2>&1 &
VERTEX_PID=$!
exec 3>"${VERTEX_FIFO}"
BG_PIDS+=("${VERTEX_PID}")
sleep 0.5

if ! kill -0 "${VERTEX_PID}" 2>/dev/null; then
    err "vertex-node failed to start"
    exit 1
fi
ok "Mesh bridge running (PID ${VERTEX_PID})"
if [[ "${INTERACTIVE}" == true ]]; then
    progress_bar 2 4 "Mesh online"
fi

if [[ "${USE_TUI}" == true ]]; then
    section_header "TUI DASHBOARD"

    info "Starting live runtime server..."
    python3 "${REPO_ROOT}/scripts/serve_live_runtime.py" --port 8765 --snapshot-dir peer-runs >/dev/null 2>&1 &
    SERVE_PID=$!
    BG_PIDS+=("${SERVE_PID}")
    sleep 0.5
    if kill -0 "${SERVE_PID}" 2>/dev/null; then
        ok "Live runtime server running (PID ${SERVE_PID})"
    else
        warn "Live runtime server failed to start"
    fi

    if command -v bun &>/dev/null; then
        info "Starting TUI dashboard..."
        bun "${REPO_ROOT}/dashboard/tui_monitor.ts" >/dev/null 2>&1 &
    TUI_PID=$!
    BG_PIDS+=("${TUI_PID}")
        sleep 0.5
        if kill -0 "${TUI_PID}" 2>/dev/null; then
            ok "TUI dashboard running (PID ${TUI_PID})"
        else
            warn "TUI dashboard failed to start"
        fi
    else
        warn "Bun not found — skipping TUI dashboard"
    fi
fi

section_header "SWARM SIMULATION"

info "Launching swarm..."

python3 "${REPO_ROOT}/main.py" \
    --mode stub \
    --drones "${DRONES}" \
    --grid "${GRID}" \
    --duration "${DURATION}" \
    --packet-loss "${PACKET_LOSS}" \
    --tick-seconds 1

if [[ "${INTERACTIVE}" == true ]]; then
    progress_bar 4 4 "Mission complete"
    printf '\n'
    section_header "MISSION COMPLETE"
    printf '  %s[✓]%s Swarm simulation finished successfully\n' "${C_GREEN}" "${C_RESET}"
    printf '  %s[✓]%s Consensus proofs emitted\n' "${C_GREEN}" "${C_RESET}"
    printf '  %s[✓]%s All systems nominal\n' "${C_GREEN}" "${C_RESET}"
    printf '\n'
    typewrite "  ${C_DIM}Entropy Hunt — Vertex Swarm Challenge 2026${C_RESET}" 0.01
    printf '\n\n'
else
    ok "[DEMO] Complete"
fi

exit 0
