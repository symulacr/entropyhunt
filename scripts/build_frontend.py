from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
from html import escape
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("build_frontend")

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"
ARTIFACT_DIR = FRONTEND_DIR / "artifacts"


class BuildError(Exception):
    pass


def _load_payload() -> dict[str, Any]:
    artifact = ARTIFACT_DIR / "final_map.json"
    if not artifact.exists():
        logger.info("Artifact %s not found; triggering auto-generation…", artifact)
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable,
            str(ROOT / "main.py"),
            "--duration=5",
            f"--final-map={artifact}",
            f"--svg-map={ARTIFACT_DIR / 'final_map.svg'}",
            f"--final-html={ARTIFACT_DIR / 'final_map.html'}",
        ]
        logger.info("Running: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), check=False)
        if result.returncode != 0:
            raise BuildError(
                f"Auto-generation failed (exit {result.returncode}).\n"
                f"Command: {' '.join(cmd)}\n"
                f"stderr: {result.stderr[:800]}"
            )
        if not artifact.exists():
            raise BuildError(f"Build prerequisite still missing after auto-generation: {artifact}")
        logger.info("Auto-generation completed successfully.")
    try:
        payload = json.loads(artifact.read_text())
    except json.JSONDecodeError as exc:
        raise BuildError(f"Invalid JSON in {artifact}: {exc}") from exc
    return payload


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
        (
            "coverage completed",
            f"{summary.get('coverage_completed', summary.get('coverage', 0))}",
            "portion of cells fully closed out in the run",
        ),
        (
            "coverage current",
            f"{summary.get('coverage_current', summary.get('coverage', 0))}",
            "live end-of-run coverage after decay",
        ),
        (
            "consensus rounds",
            summary.get("consensus_rounds", 0),
            "deterministic claim-resolution rounds executed",
        ),
        ("dropouts", summary.get("dropouts", 0), "scheduled failures observed during the run"),
        (
            "survivor found",
            summary.get("survivor_found", False),
            "target confirmation was published to the swarm",
        ),
        (
            "mesh messages",
            summary.get("mesh_messages", 0),
            "local bus publications captured in the stub",
        ),
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
                ],
            ),
        )
    return "".join(rendered)


def _artifact_links() -> str:
    links = [
        (
            "./artifacts/final_map.json",
            "Replay payload",
            "load this into the packaged replay console",
        ),
        ("./artifacts/final_map.svg", "Heatmap SVG", "standalone snapshot for docs or slides"),
        ("./artifacts/final_map.html", "Final dashboard", "self-contained HTML snapshot"),
        (
            "./console.html",
            "Replay console",
            "read-only replay viewer; live mode still needs local helper scripts",
        ),
    ]
    return "".join(
        f'<li><a href="{href}">{escape(label)}</a> — {escape(note)}</li>'
        for href, label, note in links
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
                    f'<span class="event-type '
                    f'{_event_class(event_type)}">{escape(event_type)}</span>',
                    f"<strong>t={escape(str(event.get('t', 0)))}s</strong> "
                    f"— {escape(str(event.get('message', '')))}",
                    "</li>",
                ],
            ),
        )
    return "".join(rendered)


def _run_meta(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    config = payload.get("config", {})
    return (
        f"Run duration <strong>{escape(str(summary.get('duration_elapsed', 0)))}s</strong>, "
        f"grid <strong>{escape(str(config.get('grid', 'n/a')))}×"
        f"{escape(str(config.get('grid', 'n/a')))}</strong>, "
        f"search increment <strong>"
        f"{escape(_format_metric(config.get('search_increment', 'n/a')))}</strong>, "
        f"completion certainty <strong>"
        f"{escape(_format_metric(config.get('completion_certainty', 'n/a')))}</strong>."
    )


def build_site(out_dir: Path) -> None:
    logger.info("Loading payload…")
    payload = _load_payload()
    summary = payload["summary"]
    events = payload.get("events", [])
    svg_artifact = ARTIFACT_DIR / "final_map.svg"
    svg_preview = (
        svg_artifact.read_text()
        if svg_artifact.exists()
        else "<p>Missing final_map.svg — run the simulation with --svg-map to generate it.</p>"
    )

    logger.info("Preparing output directory: %s", out_dir)
    if out_dir.exists():
        logger.info("Removing existing output directory…")
        shutil.rmtree(out_dir)
    (out_dir / "assets").mkdir(parents=True)
    (out_dir / "artifacts").mkdir(parents=True)

    files_to_copy = [
        (FRONTEND_DIR / "assets" / "shell.css", out_dir / "assets" / "shell.css"),
        (FRONTEND_DIR / "console_source.html", out_dir / "console.html"),
        (FRONTEND_DIR / "live.html", out_dir / "live.html"),
        (ARTIFACT_DIR / "final_map.json", out_dir / "artifacts" / "final_map.json"),
        (ARTIFACT_DIR / "final_map.svg", out_dir / "artifacts" / "final_map.svg"),
        (ARTIFACT_DIR / "final_map.html", out_dir / "artifacts" / "final_map.html"),
    ]
    for src, dst in files_to_copy:
        if src.exists():
            logger.info("Copying %s → %s", src.relative_to(ROOT), dst.relative_to(out_dir))
            shutil.copy2(src, dst)
        else:
            logger.warning("Missing source file: %s", src)

    template = (FRONTEND_DIR / "index.template.html").read_text()
    html = (
        template.replace("{{SUMMARY_CARDS}}", _summary_cards(summary))
        .replace("{{RUN_META}}", _run_meta(payload))
        .replace("{{ARTIFACT_LINKS}}", _artifact_links())
        .replace("{{SVG_PREVIEW}}", svg_preview)
        .replace("{{RECENT_EVENTS}}", _recent_events(events))
    )
    if "{{" in html:
        remaining = [m for m in __import__("re").finditer(r"\{\{.*?\}\}", html)]
        raise BuildError(
            f"Unresolved template placeholders in output: "
            f"{', '.join(m.group(0) for m in remaining)}"
        )
    (out_dir / "index.html").write_text(html)
    logger.info("Wrote %s", out_dir / "index.html")
    logger.info("Build complete.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the packaged Entropy Hunt frontend shell")
    parser.add_argument("--out-dir", default="frontend/dist")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        build_site((ROOT / args.out_dir).resolve())
    except BuildError as exc:
        logger.error("Build failed: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Unexpected build error: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
