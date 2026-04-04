from __future__ import annotations

from html import escape

from auction.voronoi import PartitionSeed, boundary_cells, ownership_grid
from core.certainty_map import CertaintyMap, Coordinate, shannon_entropy
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


def render_svg_heatmap(
    certainty_map: CertaintyMap,
    drones: list[DroneState],
    *,
    cell_px: int = 28,
    target: Coordinate | None = None,
    boundary_cells: tuple[Coordinate, ...] | None = None,
    boundary_cells_override: tuple[Coordinate, ...] | None = None,
    show_voronoi: bool = True,
) -> str:
    width = certainty_map.size * cell_px
    height = certainty_map.size * cell_px
    alive_drones = [drone for drone in drones if drone.alive]
    if boundary_cells_override is not None:
        boundaries = set(boundary_cells_override)
    elif boundary_cells is None:
        seeds = [PartitionSeed(drone.drone_id, drone.position) for drone in alive_drones]
        boundaries = set(
            boundary_cells_fn(ownership_grid(seeds, size=certainty_map.size))
            if show_voronoi and len(seeds) > 1
            else tuple()
        )
    else:
        boundaries = set(boundary_cells)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#ffffff" />',
    ]

    for y in range(certainty_map.size):
        for x in range(certainty_map.size):
            cell = certainty_map.cell((x, y))
            entropy = shannon_entropy(cell.certainty)
            intensity = int(255 - entropy * 210)
            fill = f"rgb({intensity},{intensity},{intensity})"
            stroke = "#dadde2" if (x, y) not in boundaries else "#8f4fd5"
            stroke_width = 0.7 if (x, y) not in boundaries else 1.6
            if target == (x, y):
                stroke = "#16a34a"
                stroke_width = 2.0
            parts.append(
                f'<rect x="{x * cell_px}" y="{y * cell_px}" width="{cell_px}" height="{cell_px}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" />'
            )

    for drone in alive_drones:
        cx = drone.position[0] * cell_px + cell_px / 2
        cy = drone.position[1] * cell_px + cell_px / 2
        label = escape(drone.drone_id)
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{cell_px * 0.22:.1f}" fill="#2563eb" stroke="#0f172a" stroke-width="1.5" />'
        )
        parts.append(
            f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" font-size="10" font-family="monospace" fill="#ffffff">{label[-1]}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


def render_html_snapshot(
    *,
    title: str,
    summary: dict[str, object],
    svg_heatmap: str,
    events: list[dict[str, object]],
) -> str:
    event_items = "".join(
        f"<li><strong>{escape(str(event.get('type', 'info'))).upper()}</strong> t={escape(str(event.get('t', 0)))}s — {escape(str(event.get('message', '')))}</li>"
        for event in events[-12:]
    )
    summary_items = "".join(
        f"<li><strong>{escape(str(key))}</strong>: {escape(str(value))}</li>"
        for key, value in summary.items()
        if key != "drones"
    )
    return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>{escape(title)}</title>
    <style>
      body {{ font-family: Inter, system-ui, sans-serif; margin: 24px; color: #111827; }}
      .layout {{ display: grid; grid-template-columns: minmax(320px, 1fr) 340px; gap: 24px; align-items: start; }}
      .panel {{ border: 1px solid #d1d5db; border-radius: 12px; padding: 16px; background: #fff; }}
      h1, h2 {{ margin: 0 0 12px; }}
      ul {{ margin: 0; padding-left: 18px; }}
      li {{ margin: 6px 0; }}
      .meta {{ color: #6b7280; margin-bottom: 16px; }}
      svg {{ width: 100%; height: auto; }}
    </style>
  </head>
  <body>
    <h1>{escape(title)}</h1>
    <p class=\"meta\">Generated from the local Entropy Hunt simulation.</p>
    <div class=\"layout\">
      <div class=\"panel\">{svg_heatmap}</div>
      <div class=\"panel\">
        <h2>Summary</h2>
        <ul>{summary_items}</ul>
        <h2 style=\"margin-top:20px\">Recent events</h2>
        <ul>{event_items or '<li>No events recorded.</li>'}</ul>
      </div>
    </div>
  </body>
</html>
"""


boundary_cells_fn = boundary_cells
