from __future__ import annotations

import json
from pathlib import Path


VERCEL_DOC = Path("docs/vercel-deploy.md")
QA_DOC = Path("docs/frontend-qa-checklist.md")


def test_vercel_config_targets_packaged_shell() -> None:
    payload = json.loads(Path("vercel.json").read_text())
    assert payload["$schema"] == "https://openapi.vercel.sh/vercel.json"
    assert payload["buildCommand"] == "bun run build"
    assert payload["outputDirectory"] == "dist"
    assert payload["bunVersion"] == "1.x"


def test_package_scripts_include_vercel_deploy_commands() -> None:
    payload = json.loads(Path("package.json").read_text())
    scripts = payload["scripts"]
    assert scripts["deploy:preview"] == "bun run build && npx vercel@latest deploy"
    assert scripts["deploy:prod"] == "bun run build && npx vercel@latest deploy --prod"


def test_docs_match_bun_first_build_and_deploy_contract() -> None:
    vercel_doc = VERCEL_DOC.read_text()
    qa_doc = QA_DOC.read_text()

    assert "bun run build" in vercel_doc
    assert "bun run deploy:preview" in vercel_doc
    assert "bun run deploy:prod" in vercel_doc
    assert "npx vercel@latest" in vercel_doc
    assert "npm run build" not in vercel_doc
    assert "npm run deploy:preview" not in vercel_doc
    assert "npm run deploy:prod" not in vercel_doc

    assert "bun run build" in qa_doc
    assert "bun run preview" in qa_doc
    assert "bun run live:peers" in qa_doc
    assert "bun run live:serve" in qa_doc
    assert "npm run build" not in qa_doc
    assert "npm run preview" not in qa_doc
