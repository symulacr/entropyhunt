from __future__ import annotations

from core.certainty_map import CertaintyMap, shannon_entropy
from roles.searcher import DroneState


def render_ascii_heatmap(certainty_map: CertaintyMap, drones: list[DroneState]) -> str:
    drone_positions = {drone.position: drone.drone_id[-1] for drone in drones if drone.alive}
    rows: list[str] = []
    for y in range(certainty_map.size):
        rendered: list[str] = []
        for x in range(certainty_map.size):
            coordinate = (x, y)
            if coordinate in drone_positions:
                rendered.append(drone_positions[coordinate])
                continue
            entropy = shannon_entropy(certainty_map.cell(coordinate).certainty)
            if entropy >= 0.95:
                rendered.append("H")
            elif entropy >= 0.6:
                rendered.append("M")
            elif entropy >= 0.25:
                rendered.append("L")
            else:
                rendered.append(".")
        rows.append(" ".join(rendered))
    return "\n".join(rows)
