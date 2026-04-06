from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path
import shutil
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"
ARTIFACT_DIR = ROOT


def _load_payload() -> dict[str, Any]:
    return json.loads((ARTIFACT_DIR / "final_map.json").read_text())


def _format_metric(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _event_class(event_type: str) -> str:
    return "ok" if event_type in {"survivor", "survivor_ack", "zone_complete"} else ""


def _summary_cards(summary: dict[str, Any]) -> str:
    cards = [
        ("coverage completed", f"{summary.get('coverage_completed', summary.get('coverage', 0))}", "portion of cells fully closed out in the run"),
        ("coverage current", f"{summary.get('coverage_current', summary.get('coverage', 0))}", "live end-of-run coverage after decay"),
        ("BFT rounds", summary.get("bft_rounds", 0), "deterministic claim-resolution rounds executed"),
        ("dropouts", summary.get("dropouts", 0), "scheduled failures observed during the run"),
        ("survivor found", summary.get("survivor_found", False), "target confirmation was published to the swarm"),
        ("mesh messages", summary.get("mesh_messages", 0), "local bus publications captured in the stub"),
    ]
    rendered: list[str] = []
    for label, value, note in cards:
        rendered.append(
            "".join(
                [
                    '<article class="card">',
                    f'<p class="card-label">{escape(label)}</p>',
                    f'<p class="card-value">{escape(_format_metric(value))}</p>',
                    f'<p class="card-note">{escape(note)}</p>',
                    "</article>",
                ]
            )
        )
    return "".join(rendered)


def _artifact_links() -> str:
    links = [
        ("./artifacts/final_map.json", "Replay payload", "load this into the packaged replay console"),
        ("./artifacts/final_map.svg", "Heatmap SVG", "standalone snapshot for docs or slides"),
        ("./artifacts/final_map.html", "Final dashboard", "self-contained HTML snapshot"),
        ("./console.html", "Replay console", "read-only replay viewer; live mode still needs local helper scripts"),
    ]
    return "".join(
        f'<li><a href="{href}">{escape(label)}</a> — {escape(note)}</li>' for href, label, note in links
    )


def _recent_events(events: list[dict[str, Any]]) -> str:
    recent = events[-8:]
    if not recent:
        return "<li>No events recorded.</li>"
    rendered: list[str] = []
    for event in reversed(recent):
        event_type = str(event.get("type", "info"))
        rendered.append(
            "".join(
                [
                    "<li>",
                    f'<span class="event-type {_event_class(event_type)}">{escape(event_type)}</span>',
                    f'<strong>t={escape(str(event.get("t", 0)))}s</strong> — {escape(str(event.get("message", "")))}',
                    "</li>",
                ]
            )
        )
    return "".join(rendered)


def _run_meta(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    config = payload.get("config", {})
    return (
        f"Run duration <strong>{escape(str(summary.get('duration_elapsed', 0)))}s</strong>, "
        f"grid <strong>{escape(str(config.get('grid', 'n/a')))}×{escape(str(config.get('grid', 'n/a')))}</strong>, "
        f"search increment <strong>{escape(_format_metric(config.get('search_increment', 'n/a')))}</strong>, "
        f"completion certainty <strong>{escape(_format_metric(config.get('completion_certainty', 'n/a')))}</strong>."
    )


def build_site(out_dir: Path) -> None:
    payload = _load_payload()
    summary = payload["summary"]
    events = payload.get("events", [])
    svg_preview = (ARTIFACT_DIR / "final_map.svg").read_text() if (ARTIFACT_DIR / "final_map.svg").exists() else "<p>Missing final_map.svg</p>"

    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "assets").mkdir(parents=True)
    (out_dir / "artifacts").mkdir(parents=True)

    shutil.copy2(FRONTEND_DIR / "assets" / "shell.css", out_dir / "assets" / "shell.css")
    shutil.copy2(ROOT / "entropy_hunt_v2.html", out_dir / "console.html")
    shutil.copy2(ROOT / "final_map.json", out_dir / "artifacts" / "final_map.json")
    shutil.copy2(ROOT / "final_map.svg", out_dir / "artifacts" / "final_map.svg")
    shutil.copy2(ROOT / "final_map.html", out_dir / "artifacts" / "final_map.html")

    template = (FRONTEND_DIR / "index.template.html").read_text()
    html = (
        template.replace("{{SUMMARY_CARDS}}", _summary_cards(summary))
        .replace("{{RUN_META}}", _run_meta(payload))
        .replace("{{ARTIFACT_LINKS}}", _artifact_links())
        .replace("{{SVG_PREVIEW}}", svg_preview)
        .replace("{{RECENT_EVENTS}}", _recent_events(events))
    )
    (out_dir / "index.html").write_text(html)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the packaged Entropy Hunt frontend shell")
    parser.add_argument("--out-dir", default="dist")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    build_site((ROOT / args.out_dir).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
