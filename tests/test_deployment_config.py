from __future__ import annotations

import json
from pathlib import Path


def test_vercel_config_targets_packaged_shell() -> None:
    payload = json.loads(Path("vercel.json").read_text())
    assert payload["$schema"] == "https://openapi.vercel.sh/vercel.json"
    assert payload["buildCommand"] == "npm run build"
    assert payload["outputDirectory"] == "dist"
