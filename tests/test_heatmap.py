from core.certainty_map import CertaintyMap
from roles.searcher import DroneState
from viz.heatmap import render_html_snapshot, render_svg_heatmap


def test_svg_and_html_snapshot_render() -> None:
    certainty_map = CertaintyMap(2)
    drones = [DroneState(drone_id="drone_1", position=(0, 0))]
    svg = render_svg_heatmap(certainty_map, drones, target=(1, 1))
    html = render_html_snapshot(
        title="Entropy Hunt",
        summary={"coverage": 1.0},
        svg_heatmap=svg,
        events=[{"type": "mesh", "t": 0, "message": "ready"}],
    )
    assert svg.startswith("<svg")
    assert "Entropy Hunt" in html
    assert "ready" in html
