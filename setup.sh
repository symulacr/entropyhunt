#!/usr/bin/env bash
# Entropy Hunt — Setup Script
# Usage: ./setup.sh [--help]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"

cd "${REPO_ROOT}"

# ── Helpers ──────────────────────────────────────────────────────────────────

info()  { printf '\033[1;34m[INFO]\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m[OK]\033[0m   %s\n' "$*"; }
warn()  { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }
err()   { printf '\033[1;31m[ERR]\033[0m  %s\n' "$*" >&2; }

print_help() {
    cat <<'EOF'
Entropy Hunt — Setup Script

Usage: ./setup.sh [OPTIONS]

Options:
  --help    Show this help message and exit

Description:
  Checks prerequisites, installs Python dependencies (pip install -e .),
  installs Bun dependencies if package.json exists, and creates .env from
  .env.example if missing.

Prerequisites checked:
  • Python 3.10+ (3.12+ recommended)
  • pip
  • Bun (optional — required for dashboard/frontend build)
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

# ── Parse flags ──────────────────────────────────────────────────────────────

if [[ "${1:-}" == "--help" ]]; then
    print_help
    exit 0
fi

if [[ $# -gt 0 ]]; then
    err "Unknown argument: $1"
    print_help
    exit 1
fi

# ── Banner ───────────────────────────────────────────────────────────────────

cat <<'EOF'
╔══════════════════════════════════════════════════════════════╗
║           Entropy Hunt — Search & Rescue Swarms              ║
║                  Setup Environment                           ║
╚══════════════════════════════════════════════════════════════╝
EOF

# ── Check Python ─────────────────────────────────────────────────────────────

info "Checking Python version..."
require_command python3 "Python 3"

PYTHON_VERSION_RAW="$(python3 --version 2>&1 | awk '{print $2}')"
PYTHON_MAJOR="$(echo "${PYTHON_VERSION_RAW}" | cut -d. -f1)"
PYTHON_MINOR="$(echo "${PYTHON_VERSION_RAW}" | cut -d. -f2)"

if [[ "${PYTHON_MAJOR}" -lt 3 ]] || { [[ "${PYTHON_MAJOR}" -eq 3 ]] && [[ "${PYTHON_MINOR}" -lt 10 ]]; }; then
    err "Python 3.10+ is required. Found: ${PYTHON_VERSION_RAW}"
    exit 1
fi

if [[ "${PYTHON_MAJOR}" -eq 3 ]] && [[ "${PYTHON_MINOR}" -lt 12 ]]; then
    warn "Python ${PYTHON_VERSION_RAW} found. Python 3.12+ is recommended."
else
    ok "Python ${PYTHON_VERSION_RAW}"
fi

# ── Check pip ────────────────────────────────────────────────────────────────

info "Checking pip..."
require_command pip "pip"
ok "pip available"

# ── Install Python dependencies ──────────────────────────────────────────────

info "Installing Python package in editable mode..."
if python3 -c "import main" 2>/dev/null; then
    ok "Python package already importable — skipping pip install"
elif pip install -e "${REPO_ROOT}" &>/dev/null; then
    ok "Python dependencies installed"
elif pip install --break-system-packages -e "${REPO_ROOT}" &>/dev/null; then
    ok "Python dependencies installed (used --break-system-packages)"
else
    err "Failed to install Python package. Try: pip install -e ."
    exit 1
fi

# ── Check / install Bun dependencies ─────────────────────────────────────────

if [[ -f "${REPO_ROOT}/package.json" ]]; then
    info "Checking Bun..."
    if command -v bun &>/dev/null; then
        ok "Bun available"
        info "Installing Bun dependencies..."
        cd "${REPO_ROOT}"
        if ! bun install &>/dev/null; then
            warn "Bun install failed — dashboard/frontend may not work"
        else
            ok "Bun dependencies installed"
        fi
    else
        warn "Bun not found. Install from https://bun.sh to build dashboard/frontend."
    fi
else
    info "No package.json found — skipping Bun setup"
fi

# ── Create .env if missing ───────────────────────────────────────────────────

if [[ ! -f "${REPO_ROOT}/.env" ]]; then
    if [[ -f "${REPO_ROOT}/.env.example" ]]; then
        info "Creating .env from .env.example..."
        cp "${REPO_ROOT}/.env.example" "${REPO_ROOT}/.env"
        ok ".env created — edit it to set your secrets"
    else
        warn ".env.example not found — skipping .env creation"
    fi
else
    ok ".env already exists"
fi

# ── Status summary ───────────────────────────────────────────────────────────

cat <<EOF

╔══════════════════════════════════════════════════════════════╗
║                     Setup Complete!                          ║
╠══════════════════════════════════════════════════════════════╣
║  Python:  ${PYTHON_VERSION_RAW}                               
║  Repo:    ${REPO_ROOT}                                        
║  Next:    Run ./demo.sh to see the live swarm demo           ║
╚══════════════════════════════════════════════════════════════╝
EOF

exit 0
