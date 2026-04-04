from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def test_frontend_build_creates_packaged_shell(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    out_dir = tmp_path / "dist"
    subprocess.run(
        [sys.executable, str(root / "scripts" / "build_frontend.py"), "--out-dir", str(out_dir)],
        cwd=root,
        check=True,
    )

    assert (out_dir / "index.html").exists()
    assert (out_dir / "console.html").exists()
    assert (out_dir / "mockup.html").exists()
    assert (out_dir / "artifacts" / "final_map.json").exists()
    assert "Latest verified run" in (out_dir / "index.html").read_text()
