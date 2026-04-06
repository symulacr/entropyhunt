from __future__ import annotations

from dataclasses import dataclass
from typing import Any


RESET = "\033[0m"
CLEAR = "\033[H\033[J"
BLACK_FG = "\033[30m"
WHITE_FG = "\033[97m"
CELL_COLORS = {
    "high": "\033[100m",
    "medium": "\033[47m",
    "low": "\033[107m",
}
GREEN_BG = "\033[102m"
DRONE_BACKGROUNDS = (
    "\033[44m",
    "\033[42m",
    "\033[43m",
    "\033[41m",
    "\033[45m",
)


@dataclass(slots=True)
class TUIDashboard:
    max_events: int = 8
    tick_delay_seconds: float = 0.02

    @staticmethod
    def _display_status(raw_status: str) -> str:
        status_map = {
            "transiting": "transit",
            "claiming": "transit",
            "claim_won": "searching",
            "claim_lost": "transit",
            "stale": "OFFLINE",
        }
        return status_map.get(raw_status, raw_status or "idle")

    def _cell_background(self, entropy: float) -> str:
        if entropy > 0.7:
            return CELL_COLORS["high"]
        if entropy >= 0.4:
            return CELL_COLORS["medium"]
        return CELL_COLORS["low"]

    def _drone_token(self, drone_id: str) -> str:
        try:
            index = max(0, int(drone_id.rsplit("_", maxsplit=1)[1]) - 1)
        except (IndexError, ValueError):
            index = 0
        background = DRONE_BACKGROUNDS[index % len(DRONE_BACKGROUNDS)]
        label = f"D{index + 1}"[:2].ljust(2)
        return f"{background}{WHITE_FG}{label} {RESET}"

    def _target_drone_token(self, drone_id: str) -> str:
        try:
            index = max(0, int(drone_id.rsplit("_", maxsplit=1)[1]) - 1)
        except (IndexError, ValueError):
            index = 0
        label = f"D{index + 1}"[:2].ljust(2)
        return f"{GREEN_BG}{BLACK_FG}{label} {RESET}"

    def _cell_token(self, entropy: float) -> str:
        background = self._cell_background(entropy)
        return f"{background}{BLACK_FG}   {RESET}"

    def _target_cell_token(self, entropy: float, flash_target: bool) -> str:
        if flash_target:
            return f"{GREEN_BG}{BLACK_FG}   {RESET}"
        return self._cell_token(entropy)

    def build_frame(self, sim_state: dict[str, Any]) -> str:
        grid: list[list[dict[str, Any]]] = sim_state.get("grid", [])
        drones: list[dict[str, Any]] = sim_state.get("drones", [])
        events: list[dict[str, Any]] = list(sim_state.get("events", []))[: self.max_events]
        target_value = sim_state.get("target", [None, None])
        target = tuple(target_value) if isinstance(target_value, (list, tuple)) else (None, None)
        flash_target = bool(sim_state.get("flash_target", False))
        drone_positions = {
            tuple(drone.get("position", ())): str(drone.get("id", "drone_1"))
            for drone in drones
            if drone.get("alive", True)
        }

        coverage = round(float(sim_state.get("coverage", 0)))
        avg_entropy = float(sim_state.get("avg_entropy", 0.0))
        auctions = int(sim_state.get("auctions", 0))
        dropouts = int(sim_state.get("dropouts", 0))
        bft_rounds = int(sim_state.get("bft_rounds", 0))
        elapsed = int(sim_state.get("elapsed", 0))
        mesh_mode = str(sim_state.get("mesh", "stub"))

        lines = [
            (
                "ENTROPY HUNT | "
                f"t={elapsed:03d}s | cov={coverage:02d}% | H={avg_entropy:.2f} | "
                f"auctions={auctions} | dropouts={dropouts} | bft={bft_rounds:03d} | mesh={mesh_mode}"
            ),
            "",
        ]

        for y, row in enumerate(grid):
            rendered: list[str] = []
            for x, cell in enumerate(row):
                drone_id = drone_positions.get((x, y))
                if drone_id is not None:
                    if (x, y) == target and flash_target:
                        rendered.append(self._target_drone_token(drone_id))
                    else:
                        rendered.append(self._drone_token(drone_id))
                    continue
                entropy = float(cell.get("entropy", 0.0))
                if (x, y) == target:
                    rendered.append(self._target_cell_token(entropy, flash_target))
                else:
                    rendered.append(self._cell_token(entropy))
            lines.append("".join(rendered))

        lines.extend(["", self._drone_line(drones), "", "EVENT LOG"])
        for event in events:
            message = str(event.get("message", "")).strip()
            event_type = str(event.get("type", "info"))
            lines.append(f"[{int(event.get('t', 0)):>3}s] {event_type}: {message}")
        return CLEAR + "\n".join(lines) + "\n"

    def _drone_line(self, drones: list[dict[str, Any]]) -> str:
        parts: list[str] = ["DRONES:"]
        for drone in drones:
            drone_id = str(drone.get("id", "drone"))
            alive = bool(drone.get("alive", True))
            if not alive:
                parts.append(f"{drone_id} OFFLINE")
                continue
            position = tuple(drone.get("position", ("--", "--")))
            target = drone.get("target")
            target_text = (
                f"[{target[0]},{target[1]}]" if isinstance(target, (list, tuple)) else "[--,--]"
            )
            status = self._display_status(str(drone.get("status", "idle")))
            entropy = float(drone.get("current_entropy", 0.0))
            parts.append(
                f"{drone_id} [{position[0]},{position[1]}]→{target_text} {status} H={entropy:.2f}"
            )
        return " | ".join(parts)

    def render(self, sim_state: dict[str, Any]) -> None:
        print(self.build_frame(sim_state), end="", flush=True)
