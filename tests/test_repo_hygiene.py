from __future__ import annotations

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def _ignored(path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", path],
        cwd=ROOT,
        check=False,
    )
    return result.returncode == 0


def test_core_source_and_product_files_are_not_gitignored() -> None:
    for path in [
        "README.md",
        "docs/frontend-qa-checklist.md",
        "package.json",
        "frontend/assets/shell.css",
        "frontend/index.template.html",
        "pyproject.toml",
        "vercel.json",
        "ros2_ws/src/entropy_hunt_interfaces/package.xml",
        "ros2_ws/src/entropy_hunt_ros2/setup.py",
        "webots_world/entropy_hunt.wbt",
        "dashboard/__fixtures__/tui_monitor_map.txt",
    ]:
        assert _ignored(path) is False, path


def test_generated_or_local_noise_remains_gitignored() -> None:
    for path in [
        ".omx/logs/example.jsonl",
        "peer-runs/demo.json",
        "runtime/sessions/demo/snapshot.json",
        "final_map.json",
        "test-final-map.json",
        "critic.md",
        "entropy_hunt.md",
        "entropy_hunt_mockup.html",
        "webots_world/README.md",
        "__pycache__/x.pyc",
    ]:
        assert _ignored(path) is True, path


def test_vercelignore_exists_and_filters_local_runtime_noise() -> None:
    text = (ROOT / ".vercelignore").read_text()
    for pattern in [
        ".omx/",
        "peer-runs/",
        "runtime/sessions/",
        "proofs.jsonl",
        "critic.md",
        "entropy_hunt.md",
        "entropy_hunt_mockup.html",
        "tests/",
        "tests_ros/",
        "webots_world/README.md",
    ]:
        assert pattern in text
