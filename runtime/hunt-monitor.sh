#!/usr/bin/env sh
set -eu
if [ -n "${npm_lifecycle_event:-}" ] && [ -t 1 ]; then
  cols="$(stty size 2>/dev/null | awk '{print $2}' || true)"
  if [ -z "$cols" ]; then cols=80; fi
  rendered="$0"
  for arg in "$@"; do
    rendered="$rendered $arg"
  done
  chars=$(( ${#rendered} + 2 ))
  lines=$(( (chars / cols) + 1 ))
  i=0
  while [ "$i" -lt "$lines" ]; do
    printf '\033[1A\033[2K\r'
    i=$((i + 1))
  done
  printf '\033[H\033[2J'
fi
export ENTROPYHUNT_WATCH_PARENT_PID="${PPID:-}"
: "${ENTROPYHUNT_EXIT_ON_SOURCE_LOSS_MS:=15000}"
export ENTROPYHUNT_EXIT_ON_SOURCE_LOSS_MS
exec bun --silent dashboard/tui_monitor_v2.ts "$@"
