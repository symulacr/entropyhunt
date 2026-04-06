from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_vercel_config_targets_bun_packaged_shell() -> None:
    payload = json.loads((ROOT / "vercel.json").read_text())
    assert payload["$schema"] == "https://openapi.vercel.sh/vercel.json"
    assert payload["buildCommand"] == "bun run build"
    assert payload["outputDirectory"] == "dist"
    assert payload["bunVersion"] == "1.x"



def test_package_scripts_include_bun_vercel_deploy_commands() -> None:
    payload = json.loads((ROOT / "package.json").read_text())
    scripts = payload["scripts"]
    assert scripts["deploy:preview"] == "bun run build && npx vercel@latest deploy"
    assert scripts["deploy:prod"] == "bun run build && npx vercel@latest deploy --prod"



def test_bun_first_operator_docs_do_not_reintroduce_npm_commands() -> None:
    expected_commands = {
        ROOT / "docs" / "vercel-deploy.md": [
            "bun run build",
            "bun run deploy:preview",
            "bun run deploy:prod",
        ],
        ROOT / "docs" / "frontend-qa-checklist.md": [
            "bun run build",
            "bun run preview",
        ],
        ROOT / "frontend" / "index.template.html": [
            "bun run build",
            "bun run preview",
            "bun run live:peers",
            "bun run live:serve",
        ],
    }

    for path, commands in expected_commands.items():
        text = path.read_text()
        assert "npm run " not in text, f"stale npm commands remain in {path.relative_to(ROOT)}"
        for command in commands:
            assert command in text, f"missing {command!r} in {path.relative_to(ROOT)}"
