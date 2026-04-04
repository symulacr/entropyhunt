from __future__ import annotations

import json
from pathlib import Path


def test_vercel_config_targets_packaged_shell() -> None:
    payload = json.loads(Path("vercel.json").read_text())
    assert payload["$schema"] == "https://openapi.vercel.sh/vercel.json"
    assert payload["buildCommand"] == "npm run build"
    assert payload["outputDirectory"] == "dist"



def test_package_scripts_include_vercel_deploy_commands() -> None:
    import json

    payload = json.loads(Path("package.json").read_text())
    scripts = payload["scripts"]
    assert scripts["deploy:preview"] == "npm run build && npx vercel@latest deploy"
    assert scripts["deploy:prod"] == "npm run build && npx vercel@latest deploy --prod"
