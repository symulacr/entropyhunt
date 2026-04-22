from __future__ import annotations

import logging
import re
import shutil
import sys
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Reset / style
RESET = "\033[0m"
CLEAR = "\033[H\033[J"
BOLD = "\033[1m"
DIM = "\033[2m"

# Muted foregrounds
FG_MUTED = "\033[38;5;245m"
FG_DIM = "\033[38;5;240m"
FG_ACCENT = "\033[38;5;81m"
FG_WARN = "\033[38;5;214m"
FG_ERROR = "\033[38;5;204m"
FG_SUCCESS = "\033[38;5;114m"
FG_INFO = "\033[38;5;147m"

# Subtle backgrounds
BG_PANEL = "\033[48;5;235m"
BG_HEADER = "\033[48;5;234m"
BG_HIGHLIGHT = "\033[48;5;236m"
BG_INVERSE = "\033[7m"

# Border sets
H = "─"
V = "│"
TL_R = "╭"
TR_R = "╮"
BL_R = "╰"
BR_R = "╯"

TL_S = "┌"
TR_S = "┐"
BL_S = "└"
BR_S = "┘"
LJ_S = "├"
RJ_S = "┤"
TD_S = "┬"
TU_S = "┴"
CROSS_S = "┼"

H_D = "═"
V_D = "║"
TL_D = "╔"
TR_D = "╗"
BL_D = "╚"
BR_D = "╝"
LJ_D = "╠"
RJ_D = "╣"
TD_D = "╦"
TU_D = "╩"

# Status mapping
STATUS_DOT_COLORS: dict[str, str] = {
    "idle": FG_MUTED,
    "computing": FG_ACCENT,
    "claiming": FG_WARN,
    "claim_won": FG_SUCCESS,
    "claim_lost": FG_ERROR,
    "transiting": FG_INFO,
    "searching": FG_ACCENT,
    "stale": FG_ERROR,
    "offline": FG_DIM,
    "OFFLINE": FG_DIM,
}

STATUS_LABELS: dict[str, str] = {
    "idle": "idle",
    "computing": "computing",
    "claiming": "claiming",
    "claim_won": "won",
    "claim_lost": "lost",
    "transiting": "transit",
    "searching": "search",
    "stale": "offline",
    "offline": "offline",
    "OFFLINE": "offline",
}

EVENT_TYPE_COLORS: dict[str, str] = {
    "info": FG_MUTED,
    "mesh": FG_ACCENT,
    "claim": FG_WARN,
    "consensus": FG_INFO,
    "failure": FG_ERROR,
    "survivor": FG_SUCCESS,
    "waiting": FG_DIM,
}


@dataclass(slots=True)
class TUIDashboard:
    max_events: int = 8
    tick_delay_seconds: float = 0.02

    @staticmethod
    def _visible_len(text: str) -> int:
        return len(_ANSI_RE.sub("", text))

    @staticmethod
    def _lpad(text: str, width: int) -> str:
        pad = max(0, width - TUIDashboard._visible_len(text))
        return text + " " * pad

    @staticmethod
    def _truncate(text: str, width: int, suffix: str = "…") -> str:
        plain = _ANSI_RE.sub("", text)
        if len(plain) <= width:
            return text
        target = max(width - len(suffix), 0)
        visible = 0
        idx = 0
        while idx < len(text) and visible < target:
            if text[idx] == "\033" and idx + 1 < len(text) and text[idx + 1] == "[":
                end = text.find("m", idx + 2)
                if end != -1:
                    idx = end + 1
                    continue
            visible += 1
            idx += 1
        return text[:idx] + suffix + RESET

    # ── entropy cells ──────────────────────────────────────────────

    @staticmethod
    def _entropy_char(entropy: float) -> str:
        if entropy >= 0.8:
            return "◆"
        if entropy >= 0.6:
            return "█"
        if entropy >= 0.4:
            return "▓"
        if entropy >= 0.2:
            return "▒"
        return "░"

    @staticmethod
    def _entropy_fg(entropy: float) -> str:
        if entropy >= 0.8:
            return FG_SUCCESS
        if entropy >= 0.6:
            return FG_INFO
        if entropy >= 0.4:
            return FG_ACCENT
        if entropy >= 0.2:
            return FG_MUTED
        return FG_DIM

    def _cell_token(self, entropy: float) -> str:
        return f"{self._entropy_fg(entropy)}{self._entropy_char(entropy)}{RESET}"

    def _target_cell_token(self, entropy: float, *, flash_target: bool, frame_counter: int = 0) -> str:
        if flash_target and (frame_counter % 8) < 4:
            return f"{BOLD}{FG_SUCCESS}◇{RESET}"
        return self._cell_token(entropy)

    # ── drone tokens ───────────────────────────────────────────────

    @staticmethod
    def _drone_index(drone_id: str) -> int:
        try:
            return max(0, int(drone_id.rsplit("_", maxsplit=1)[1]) - 1)
        except (IndexError, ValueError):
            return 0

    def _drone_label(self, drone_id: str) -> str:
        idx = self._drone_index(drone_id)
        if idx < 9:
            return str(idx + 1)
        if idx < 35:
            return chr(ord("a") + idx - 9)
        return "+"

    def _drone_status_color(self, status: str) -> str:
        return STATUS_DOT_COLORS.get(status, FG_MUTED)

    def _drone_token(self, drone_id: str, status: str = "idle") -> str:
        label = self._drone_label(drone_id)
        color = self._drone_status_color(status)
        return f"{color}{label}{RESET}"

    def _target_drone_token(self, drone_id: str, status: str = "idle", frame_counter: int = 0) -> str:
        label = self._drone_label(drone_id)
        pulse = (frame_counter % 8) < 4
        if pulse:
            return f"{BOLD}{FG_SUCCESS}{label}{RESET}"
        color = self._drone_status_color(status)
        return f"{BOLD}{color}{label}{RESET}"

    # ── battery ────────────────────────────────────────────────────

    @staticmethod
    def _battery_bar(battery: float, width: int = 10) -> str:
        clamped = max(0.0, min(100.0, float(battery)))
        filled = int((clamped / 100.0) * width)
        empty = width - filled
        if clamped > 60:
            color = FG_SUCCESS
        elif clamped >= 30:
            color = FG_WARN
        else:
            color = FG_ERROR
        bar = "█" * filled + "░" * empty
        return f"{color}[{bar}] {clamped:.0f}%{RESET}"

    @staticmethod
    def _battery_compact(battery: float) -> str:
        clamped = max(0.0, min(100.0, float(battery)))
        if clamped > 60:
            color = FG_SUCCESS
        elif clamped >= 30:
            color = FG_WARN
        else:
            color = FG_ERROR
        return f"{color}{clamped:.0f}%{RESET}"

    # ── data helpers ───────────────────────────────────────────────

    def _collect_drone_positions(self, drones: list[dict[str, Any]]) -> dict[tuple[int, int], tuple[str, str]]:
        positions: dict[tuple[int, int], tuple[str, str]] = {}
        for drone in drones:
            if not drone.get("alive", True):
                continue
            pos = drone.get("position")
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                positions[(int(pos[0]), int(pos[1]))] = (
                    str(drone.get("id", "drone")),
                    str(drone.get("status", "idle")),
                )
        return positions

    # ── panels ─────────────────────────────────────────────────────

    def _system_panel(self, sim_state: dict[str, Any], width: int) -> str:
        elapsed = int(sim_state.get("elapsed", 0))
        coverage = round(float(sim_state.get("coverage", 0)))
        coverage_completed = round(float(sim_state.get("coverage_completed", 0)) * 100)
        coverage_visited = round(float(sim_state.get("coverage_visited", 0)) * 100)
        avg_entropy = float(sim_state.get("avg_entropy", 0.0))
        auctions = int(sim_state.get("auctions", 0))
        dropouts = int(sim_state.get("dropouts", 0))
        consensus_rounds = int(sim_state.get("consensus_rounds", 0))
        survivor_found = bool(sim_state.get("survivor_found", False))
        survivor_receipts = int(sim_state.get("survivor_receipts", 0))
        tick_seconds = sim_state.get("tick_seconds")
        tick_delay = sim_state.get("tick_delay_seconds")

        parts = [
            f"{FG_MUTED}t{RESET}={elapsed:03d}s",
            f"{FG_MUTED}cov{RESET}={coverage:02d}%",
            f"{FG_MUTED}H{RESET}={avg_entropy:.2f}",
            f"{FG_MUTED}auc{RESET}={auctions}",
            f"{FG_MUTED}drop{RESET}={dropouts}",
            f"{FG_MUTED}cns{RESET}={consensus_rounds:03d}",
        ]
        if coverage_completed > 0 or coverage_visited > 0:
            parts.append(f"{FG_MUTED}done{RESET}={coverage_completed:.0f}%")
            parts.append(f"{FG_MUTED}visit{RESET}={coverage_visited:.0f}%")
        if survivor_found:
            parts.append(f"{FG_SUCCESS}{BOLD}SURVIVOR{RESET}")
        if survivor_receipts > 0:
            parts.append(f"{FG_MUTED}acks{RESET}={survivor_receipts}")
        if tick_seconds is not None:
            parts.append(f"{FG_MUTED}tick{RESET}={tick_seconds}s")
        if tick_delay is not None:
            parts.append(f"{FG_MUTED}delay{RESET}={tick_delay:.2f}s")

        return self._truncate(" │ ".join(parts), width)

    def _grid_lines(
        self,
        grid: list[list[dict[str, Any]]],
        drone_positions: dict[tuple[int, int], tuple[str, str]],
        target: tuple[Any, Any],
        flash_target: bool,
        inner_width: int,
        frame_counter: int = 0,
    ) -> list[str]:
        if not grid:
            return ["  (no grid)"]
        lines: list[str] = []
        max_cells = max(1, inner_width)
        for y, row in enumerate(grid):
            rendered: list[str] = []
            for x in range(min(len(row), max_cells)):
                cell = row[x]
                drone = drone_positions.get((x, y))
                if drone is not None:
                    drone_id, status = drone
                    if (x, y) == target and flash_target:
                        rendered.append(self._target_drone_token(drone_id, status, frame_counter))
                    else:
                        rendered.append(self._drone_token(drone_id, status))
                    continue
                entropy = float(cell.get("entropy", 0.0))
                if (x, y) == target:
                    rendered.append(
                        self._target_cell_token(entropy, flash_target=flash_target, frame_counter=frame_counter)
                    )
                else:
                    rendered.append(self._cell_token(entropy))
            grid_line = "".join(rendered)
            visible = len(rendered)
            padding = max(0, inner_width - visible)
            lines.append(f" {grid_line}{' ' * padding}")
        return lines

    def _drone_lines(self, drones: list[dict[str, Any]], width: int, compact: bool = False) -> list[str]:
        if not drones:
            return ["  (no drones)"]
        lines: list[str] = []
        for drone in drones:
            line = self._format_drone(drone, compact=compact)
            lines.append(self._truncate(line, width))
        return lines

    def _format_drone(self, drone: dict[str, Any], compact: bool = False) -> str:
        drone_id = str(drone.get("id", "drone"))
        alive = bool(drone.get("alive", True))
        reachable = bool(drone.get("reachable", alive))
        if not alive or not reachable:
            dot = f"{FG_DIM}●{RESET}"
            return f"  {dot} {FG_DIM}{drone_id}{RESET} offline"

        position = tuple(drone.get("position", ("--", "--")))
        target = drone.get("target")
        target_text = f"[{target[0]},{target[1]}]" if isinstance(target, (list, tuple)) else "[--,--]"
        raw_status = str(drone.get("status", "idle"))
        status_label = STATUS_LABELS.get(raw_status, raw_status or "idle")
        status_color = STATUS_DOT_COLORS.get(raw_status, FG_MUTED)
        entropy = float(drone.get("current_entropy", 0.0))
        role = str(drone.get("role", "scout"))
        battery = float(drone.get("battery", -1.0))
        searched = int(drone.get("searched_cells", 0))
        subzone = drone.get("subzone")

        dot = f"{status_color}●{RESET}"

        if compact:
            parts = [
                f"  {dot} {BOLD}{drone_id}{RESET}",
                f"{FG_MUTED}{role}{RESET}",
                f"[{position[0]},{position[1]}]→{target_text}",
                f"{status_color}{status_label}{RESET}",
            ]
            if battery >= 0:
                parts.append(self._battery_compact(battery))
            return " ".join(parts)

        parts = [
            f"  {dot} {BOLD}{drone_id}{RESET}",
            f"{FG_MUTED}{role}{RESET}",
            f"[{position[0]},{position[1]}]→{target_text}",
            f"{status_color}{status_label}{RESET}",
            f"H={entropy:.2f}",
        ]
        if subzone is not None:
            parts.append(f"sz={subzone}")
        if battery >= 0:
            parts.append(self._battery_bar(battery))
        if searched > 0:
            parts.append(f"searched={searched}")
        return " ".join(parts)

    def _mesh_topology_ascii(self, mesh_peers: list[dict[str, Any]], width: int) -> list[str]:
        if not mesh_peers:
            return []
        all_peers = list(mesh_peers)

        def _peer_label(peer: dict[str, Any]) -> str:
            pid = str(peer.get("peer_id", "?"))
            if peer.get("stale"):
                return f"{FG_DIM}{pid}{RESET}"
            return f"{FG_MUTED}{pid}{RESET}"

        def _connector(peer: dict[str, Any]) -> str:
            if peer.get("stale"):
                return f"{FG_DIM}┄┄┄{RESET}"
            return f"{FG_DIM}───{RESET}"

        if len(all_peers) <= 1:
            return []

        lines: list[str] = []
        if len(all_peers) <= 4:
            labels = [_peer_label(p) for p in all_peers]
            ring_parts = []
            for i, label in enumerate(labels):
                ring_parts.append(label)
                if i < len(labels) - 1:
                    ring_parts.append(_connector(all_peers[i]))
                else:
                    ring_parts.append(_connector(all_peers[0]))
            ring_parts.append(labels[0])
            lines.append(f"  {''.join(ring_parts)}")
        else:
            active = [p for p in all_peers if not p.get("stale")]
            center = active[0] if active else all_peers[0]
            center_label = _peer_label(center)
            spokes = [_peer_label(p) for p in all_peers if p.get("peer_id") != center.get("peer_id")]
            per_row = max(3, (width - 4) // 12)
            for i in range(0, len(spokes), per_row):
                row = spokes[i : i + per_row]
                line = "  " + f"{FG_DIM}│{RESET} ".join(row)
                lines.append(line)
            lines.insert(0, f"  {center_label} {FG_DIM}◄──►{RESET} peers")

        return lines

    def _mesh_panel(self, sim_state: dict[str, Any], width: int) -> list[str]:
        mesh_mode = str(sim_state.get("mesh", "stub"))
        mesh_peers: list[dict[str, Any]] = list(sim_state.get("mesh_peers", []))
        mesh_messages = int(sim_state.get("mesh_messages", 0))
        drone_count = len(sim_state.get("drones", []))
        peer_count = len(mesh_peers)
        active_peers = sum(1 for p in mesh_peers if not p.get("stale"))

        parts = [
            f"{FG_MUTED}transport{RESET}={mesh_mode}",
            f"{FG_MUTED}peers{RESET}={active_peers}/{peer_count or drone_count}",
        ]
        if mesh_messages > 0:
            parts.append(f"{FG_MUTED}msgs{RESET}={mesh_messages:,}")

        peer_parts: list[str] = []
        for peer in mesh_peers[:6]:
            pid = str(peer.get("peer_id", "?"))
            stale = bool(peer.get("stale"))
            last_seen = int(peer.get("last_seen_ms", 0))
            indicator = f"{FG_DIM}○{RESET}" if stale else f"{FG_SUCCESS}●{RESET}"
            if last_seen > 0:
                peer_parts.append(f"{FG_MUTED}{pid}{RESET}:{last_seen}ms{indicator}")
            else:
                peer_parts.append(f"{FG_MUTED}{pid}{RESET}{indicator}")
        if peer_parts:
            parts.append("│ " + " ".join(peer_parts))

        text = " │ ".join(parts)
        lines = [self._truncate(text, width)]
        lines.extend(self._mesh_topology_ascii(mesh_peers, width))
        return lines

    def _consensus_panel(self, sim_state: dict[str, Any], width: int) -> list[str]:
        consensus_rounds = int(sim_state.get("consensus_rounds", 0))
        pending_claims: list[dict[str, Any]] = list(sim_state.get("pending_claims", []))
        consensus_entries: list[dict[str, Any]] = list(sim_state.get("consensus", []))

        parts = [
            f"{FG_MUTED}rounds{RESET}={consensus_rounds}",
            f"{FG_MUTED}pending{RESET}={len(pending_claims)}",
        ]
        if pending_claims:
            latest = pending_claims[-1]
            zone = latest.get("zone")
            owner = latest.get("owner", "?")
            zone_text = f"[{zone[0]},{zone[1]}]" if isinstance(zone, (list, tuple)) else str(zone)
            parts.append(f"latest claim {zone_text} by {owner}")

        lines = [self._truncate(" │ ".join(parts), width)]

        if consensus_entries:
            entries_text = []
            for entry in consensus_entries[-3:]:
                cell = entry.get("cell")
                cell_text = f"[{cell[0]},{cell[1]}]" if isinstance(cell, (list, tuple)) else str(cell)
                status = entry.get("status", "?")
                votes = int(entry.get("vote_count", 0))
                entries_text.append(f"{cell_text} {status} ({votes}v)")
            lines.append(self._truncate("  recent: " + " ".join(entries_text), width))

        return lines

    def _failures_panel(self, sim_state: dict[str, Any], width: int) -> list[str]:
        failures: list[dict[str, Any]] = list(sim_state.get("failures", []))
        if not failures:
            return ["  (no failures)"]

        lines: list[str] = []
        for failure in failures[-5:]:
            drone_id = str(failure.get("drone_id", "?"))
            ftype = str(failure.get("failure_type", "?"))
            t = int(failure.get("t", 0))
            recovered = bool(failure.get("recovered", False))
            rec_text = f" {FG_SUCCESS}[RECOVERED]{RESET}" if recovered else f" {FG_ERROR}[ACTIVE]{RESET}"
            line = f"  {FG_ERROR}{drone_id}{RESET} {FG_MUTED}{ftype}{RESET} @ {t}s{rec_text}"
            lines.append(self._truncate(line, width))
        return lines

    def _events_panel(self, events: list[dict[str, Any]], width: int, frame_counter: int = 0) -> list[str]:
        if not events:
            return ["  (no events)"]
        lines: list[str] = []
        for i, event in enumerate(events):
            message = str(event.get("message", "")).strip()
            event_type = str(event.get("type", "info"))
            t = int(event.get("t", 0))
            type_color = EVENT_TYPE_COLORS.get(event_type, FG_MUTED)
            prefix = f"{BG_HIGHLIGHT}" if (frame_counter % 16) < 4 and i == len(events) - 1 else ""
            line = f"{prefix}{t:>3}s  {type_color}{event_type:<8}{RESET}{FG_DIM}│{RESET} {message}"
            lines.append(self._truncate(line, width))
        return lines

    # ── border helpers ─────────────────────────────────────────────

    @staticmethod
    def _single_top(text: str, width: int) -> str:
        inner = max(0, width - 2)
        plain = _ANSI_RE.sub("", text)
        text_len = len(plain)
        pad = max(0, inner - text_len)
        return f"{TL_S}{text}{' ' * pad}{TR_S}"

    @staticmethod
    def _single_bottom(width: int) -> str:
        return f"{BL_S}{H * max(0, width - 2)}{BR_S}"

    @staticmethod
    def _single_mid(text: str, width: int) -> str:
        inner = max(0, width - 2)
        plain = _ANSI_RE.sub("", text)
        text_len = len(plain)
        pad = max(0, inner - text_len)
        return f"{V}{text}{' ' * pad}{V}"

    @staticmethod
    def _double_top(text: str, width: int) -> str:
        inner = max(0, width - 2)
        plain = _ANSI_RE.sub("", text)
        text_len = len(plain)
        pad = max(0, inner - text_len)
        return f"{TL_D}{text}{' ' * pad}{TR_D}"

    @staticmethod
    def _double_bottom(width: int) -> str:
        return f"{BL_D}{H_D * max(0, width - 2)}{BR_D}"

    @staticmethod
    def _double_mid(text: str, width: int) -> str:
        inner = max(0, width - 2)
        plain = _ANSI_RE.sub("", text)
        text_len = len(plain)
        pad = max(0, inner - text_len)
        return f"{V_D}{text}{' ' * pad}{V_D}"

    @staticmethod
    def _rounded_top(text: str, width: int) -> str:
        inner = max(0, width - 2)
        plain = _ANSI_RE.sub("", text)
        text_len = len(plain)
        pad = max(0, inner - text_len)
        return f"{TL_R}{text}{' ' * pad}{TR_R}"

    @staticmethod
    def _rounded_bottom(width: int) -> str:
        return f"{BL_R}{H * max(0, width - 2)}{BR_R}"

    @staticmethod
    def _rounded_mid(text: str, width: int) -> str:
        inner = max(0, width - 2)
        plain = _ANSI_RE.sub("", text)
        text_len = len(plain)
        pad = max(0, inner - text_len)
        return f"{V}{text}{' ' * pad}{V}"

    @staticmethod
    def _pair_top(w1: int, w2: int, tl: str, tr: str, td: str) -> str:
        return f"{tl}{H * w1}{td}{H * w2}{tr}"

    @staticmethod
    def _pair_bottom(w1: int, w2: int, bl: str, br: str, tu: str) -> str:
        return f"{bl}{H * w1}{tu}{H * w2}{br}"

    @staticmethod
    def _pair_line(left: str, right: str, w1: int, w2: int) -> str:
        pad1 = max(0, w1 - TUIDashboard._visible_len(left))
        pad2 = max(0, w2 - TUIDashboard._visible_len(right))
        return f"{V}{left}{' ' * pad1}{V}{right}{' ' * pad2}{V}"

    # ── layout builders ────────────────────────────────────────────

    def _header_lines(
        self,
        sim_state: dict[str, Any],
        width: int,
        stale_msg: str,
        paused: bool,
    ) -> list[str]:
        title = " ENTROPY HUNT "
        if paused:
            title = f" [PAUSED] {title.strip()} "
        system_text = self._system_panel(sim_state, width)
        header_text = f"{title}── {system_text}"
        # Truncate to fit width, accounting for ANSI
        header_line = self._truncate(header_text, width)
        lines = [f"{BG_HEADER}{self._lpad(header_line, width)}{RESET}"]
        if stale_msg:
            lines.append(f"{BG_HEADER}{FG_WARN}{self._lpad(stale_msg, width)}{RESET}")
        return lines

    def _footer_line(self, sim_state: dict[str, Any], width: int) -> str:
        tick_delay = sim_state.get("tick_delay_seconds", self.tick_delay_seconds)
        text = f"  [P]ause  [S]tep  [Q]uit  {FG_DIM}│{RESET}  tick={tick_delay:.2f}s  "
        return f"{BG_INVERSE}{self._lpad(text, width)}{RESET}"

    def _build_tiny_frame(
        self,
        sim_state: dict[str, Any],
        width: int,
        grid: list[list[dict[str, Any]]],
        drones: list[dict[str, Any]],
        target: tuple[Any, Any],
        flash_target: bool,
        stale_msg: str,
        paused: bool,
        frame_counter: int,
    ) -> list[str]:
        drone_positions = self._collect_drone_positions(drones)
        lines: list[str] = []
        lines.extend(self._header_lines(sim_state, width, stale_msg, paused))
        if grid:
            grid_content = self._grid_lines(grid, drone_positions, target, flash_target, width - 2, frame_counter)
            for gline in grid_content[:6]:
                lines.append(self._lpad(gline, width))
        lines.append(self._footer_line(sim_state, width))
        return lines

    def _build_narrow_frame(
        self,
        sim_state: dict[str, Any],
        width: int,
        grid: list[list[dict[str, Any]]],
        drones: list[dict[str, Any]],
        events: list[dict[str, Any]],
        target: tuple[Any, Any],
        flash_target: bool,
        stale_msg: str,
        paused: bool,
        frame_counter: int,
    ) -> list[str]:
        drone_positions = self._collect_drone_positions(drones)
        lines: list[str] = []
        lines.extend(self._header_lines(sim_state, width, stale_msg, paused))

        grid_cols = len(grid[0]) if grid else 0
        grid_w = grid_cols + 2
        drone_w = width - grid_w - 1

        if grid and drone_w >= 18:
            lines.append(self._pair_top(grid_w, drone_w, TL_R, TR_R, TD_S))
            lines.append(
                self._pair_line(
                    self._lpad(" GRID ", grid_w),
                    self._lpad(f" DRONES ({len(drones)}) ", drone_w),
                    grid_w,
                    drone_w,
                )
            )
            grid_content = self._grid_lines(grid, drone_positions, target, flash_target, grid_w - 2, frame_counter)
            drone_content = self._drone_lines(drones, drone_w - 2, compact=True)
            max_rows = max(len(grid_content), len(drone_content))
            for i in range(max_rows):
                g = grid_content[i] if i < len(grid_content) else ""
                d = drone_content[i] if i < len(drone_content) else ""
                lines.append(self._pair_line(g, d, grid_w, drone_w))
            lines.append(self._pair_bottom(grid_w, drone_w, BL_R, BR_R, TU_S))
        else:
            if grid:
                lines.append(self._rounded_top(" GRID ", width))
                for gline in self._grid_lines(grid, drone_positions, target, flash_target, width - 2, frame_counter):
                    lines.append(self._rounded_mid(gline, width))
                lines.append(self._rounded_bottom(width))
            lines.append(self._single_top(f" DRONES ({len(drones)}) ", width))
            for dline in self._drone_lines(drones, width - 2, compact=True):
                lines.append(self._single_mid(dline, width))
            lines.append(self._single_bottom(width))

        lines.append(self._single_top(" MESH ", width))
        for mline in self._mesh_panel(sim_state, width - 2):
            lines.append(self._single_mid(mline, width))
        lines.append(self._single_bottom(width))

        lines.append(self._single_top(" CONSENSUS ", width))
        for cline in self._consensus_panel(sim_state, width - 2):
            lines.append(self._single_mid(cline, width))
        lines.append(self._single_bottom(width))

        lines.append(self._double_top(" FAILURES ", width))
        for fline in self._failures_panel(sim_state, width - 2):
            lines.append(self._double_mid(fline, width))
        lines.append(self._double_bottom(width))

        lines.append(self._single_top(f" EVENTS ({len(events)}) ", width))
        for eline in self._events_panel(events, width - 2, frame_counter):
            lines.append(self._single_mid(eline, width))
        lines.append(self._single_bottom(width))

        lines.append(self._footer_line(sim_state, width))
        return lines

    def _build_medium_frame(
        self,
        sim_state: dict[str, Any],
        width: int,
        grid: list[list[dict[str, Any]]],
        drones: list[dict[str, Any]],
        events: list[dict[str, Any]],
        target: tuple[Any, Any],
        flash_target: bool,
        stale_msg: str,
        paused: bool,
        frame_counter: int,
    ) -> list[str]:
        drone_positions = self._collect_drone_positions(drones)
        lines: list[str] = []
        lines.extend(self._header_lines(sim_state, width, stale_msg, paused))

        left_w = (width - 1) // 2
        right_w = width - left_w - 1

        lines.append(self._pair_top(left_w, right_w, TL_R, TR_R, TD_S))
        lines.append(
            self._pair_line(
                self._lpad(" GRID ", left_w),
                self._lpad(f" DRONES ({len(drones)}) ", right_w),
                left_w,
                right_w,
            )
        )
        grid_content = self._grid_lines(grid, drone_positions, target, flash_target, left_w - 2, frame_counter)
        drone_content = self._drone_lines(drones, right_w - 2, compact=True)
        max_rows = max(len(grid_content), len(drone_content))
        for i in range(max_rows):
            g = grid_content[i] if i < len(grid_content) else ""
            d = drone_content[i] if i < len(drone_content) else ""
            lines.append(self._pair_line(g, d, left_w, right_w))
        lines.append(self._pair_bottom(left_w, right_w, BL_R, BR_R, TU_S))

        lines.append(self._single_top(" MESH ", width))
        for mline in self._mesh_panel(sim_state, width - 2):
            lines.append(self._single_mid(mline, width))
        lines.append(self._single_bottom(width))

        lines.append(self._single_top(" CONSENSUS ", width))
        for cline in self._consensus_panel(sim_state, width - 2):
            lines.append(self._single_mid(cline, width))
        lines.append(self._single_bottom(width))

        lines.append(self._double_top(" FAILURES ", width))
        for fline in self._failures_panel(sim_state, width - 2):
            lines.append(self._double_mid(fline, width))
        lines.append(self._double_bottom(width))

        lines.append(self._single_top(f" EVENTS ({len(events)}) ", width))
        for eline in self._events_panel(events, width - 2, frame_counter):
            lines.append(self._single_mid(eline, width))
        lines.append(self._single_bottom(width))

        lines.append(self._footer_line(sim_state, width))
        return lines

    def _build_wide_frame(
        self,
        sim_state: dict[str, Any],
        width: int,
        grid: list[list[dict[str, Any]]],
        drones: list[dict[str, Any]],
        events: list[dict[str, Any]],
        target: tuple[Any, Any],
        flash_target: bool,
        stale_msg: str,
        paused: bool,
        frame_counter: int,
    ) -> list[str]:
        drone_positions = self._collect_drone_positions(drones)
        lines: list[str] = []
        lines.extend(self._header_lines(sim_state, width, stale_msg, paused))

        left_w = (width - 1) // 2
        right_w = width - left_w - 1

        lines.append(self._pair_top(left_w, right_w, TL_R, TR_R, TD_S))
        lines.append(
            self._pair_line(
                self._lpad(" GRID ", left_w),
                self._lpad(f" DRONES ({len(drones)}) ", right_w),
                left_w,
                right_w,
            )
        )
        grid_content = self._grid_lines(grid, drone_positions, target, flash_target, left_w - 2, frame_counter)
        drone_content = self._drone_lines(drones, right_w - 2, compact=True)
        max_rows = max(len(grid_content), len(drone_content))
        for i in range(max_rows):
            g = grid_content[i] if i < len(grid_content) else ""
            d = drone_content[i] if i < len(drone_content) else ""
            lines.append(self._pair_line(g, d, left_w, right_w))
        lines.append(self._pair_bottom(left_w, right_w, BL_R, BR_R, TU_S))

        base = (width - 4) // 3
        rem = (width - 4) % 3
        mesh_w = base
        cons_w = base
        fail_w = base + rem

        lines.append(
            self._pair_top(mesh_w, cons_w + 1 + fail_w, TL_S, TR_S, TD_S)
        )
        top3 = (
            f"{TL_S}{H * mesh_w}{TD_S}{H * cons_w}{TD_S}{H * fail_w}{TR_S}"
        )
        lines.append(top3)
        lines.append(
            f"{V}{self._lpad(' MESH ', mesh_w)}{V}{self._lpad(' CONSENSUS ', cons_w)}"
            f"{V}{self._lpad(' FAILURES ', fail_w)}{V}"
        )
        mesh_content = self._mesh_panel(sim_state, mesh_w - 2)
        cons_content = self._consensus_panel(sim_state, cons_w - 2)
        fail_content = self._failures_panel(sim_state, fail_w - 2)
        max_rows = max(len(mesh_content), len(cons_content), len(fail_content))
        for i in range(max_rows):
            m = mesh_content[i] if i < len(mesh_content) else ""
            c = cons_content[i] if i < len(cons_content) else ""
            f = fail_content[i] if i < len(fail_content) else ""
            pad_m = max(0, mesh_w - self._visible_len(m))
            pad_c = max(0, cons_w - self._visible_len(c))
            pad_f = max(0, fail_w - self._visible_len(f))
            lines.append(
                f"{V}{m}{' ' * pad_m}{V}{c}{' ' * pad_c}{V}{f}{' ' * pad_f}{V}"
            )
        bottom3 = (
            f"{BL_S}{H * mesh_w}{TU_S}{H * cons_w}{TU_S}{H * fail_w}{BR_S}"
        )
        lines.append(bottom3)

        lines.append(self._single_top(f" EVENTS ({len(events)}) ", width))
        for eline in self._events_panel(events, width - 2, frame_counter):
            lines.append(self._single_mid(eline, width))
        lines.append(self._single_bottom(width))

        lines.append(self._footer_line(sim_state, width))
        return lines

    # ── public interface ───────────────────────────────────────────

    def build_frame(self, sim_state: dict[str, Any]) -> str:
        grid: list[list[dict[str, Any]]] = sim_state.get("grid", [])
        drones: list[dict[str, Any]] = sim_state.get("drones", [])
        events: list[dict[str, Any]] = list(sim_state.get("events", []))[: self.max_events]
        target_value = sim_state.get("target", [None, None])
        target = tuple(target_value) if isinstance(target_value, (list, tuple)) else (None, None)
        flash_target = bool(sim_state.get("flash_target", False))
        stale_msg = str(sim_state.get("stale_message", ""))
        paused = bool(sim_state.get("paused", False))
        frame_counter = int(sim_state.get("frame_counter", 0))

        term_cols, _term_rows = shutil.get_terminal_size()
        width = max(36, min(term_cols, 120))

        if width < 40:
            lines = self._build_tiny_frame(
                sim_state, width, grid, drones, target, flash_target, stale_msg, paused, frame_counter
            )
        elif width < 60:
            lines = self._build_narrow_frame(
                sim_state, width, grid, drones, events, target, flash_target, stale_msg, paused, frame_counter
            )
        elif width < 80:
            lines = self._build_medium_frame(
                sim_state, width, grid, drones, events, target, flash_target, stale_msg, paused, frame_counter
            )
        else:
            lines = self._build_wide_frame(
                sim_state, width, grid, drones, events, target, flash_target, stale_msg, paused, frame_counter
            )

        frame = CLEAR + "\n".join(lines) + "\n"
        return frame

    def render(self, sim_state: dict[str, Any]) -> None:
        try:
            frame = self.build_frame(sim_state)
            sys.stdout.write(frame)
            sys.stdout.flush()
        except Exception as exc:
            logger.warning("Render failed: %s", exc)
