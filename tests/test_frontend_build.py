from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_build_creates_packaged_shell(tmp_path: Path) -> None:
    out_dir = tmp_path / "dist"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_frontend.py"), "--out-dir", str(out_dir)],
        cwd=ROOT,
        check=True,
    )

    index_html = (out_dir / "index.html").read_text()

    assert (out_dir / "index.html").exists()
    assert (out_dir / "console.html").exists()
    assert (out_dir / "artifacts" / "final_map.json").exists()
    assert (out_dir / "artifacts" / "final_map.svg").exists()
    assert (out_dir / "artifacts" / "final_map.html").exists()

    assert "Latest verified run" in index_html
    assert "./console.html" in index_html
    assert "./artifacts/final_map.html" in index_html
    assert "bun run build" in index_html
    assert "bun run preview" in index_html
    assert "bun run live:peers" in index_html
    assert "bun run live:serve" in index_html
    assert "npm run " not in index_html
    assert "mockup.html" not in index_html
    assert "read-only replay viewer" in index_html
    assert "live data requires running the local helper scripts alongside it" in index_html
