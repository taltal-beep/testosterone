from __future__ import annotations

from pathlib import Path

import yaml


def test_gitlab_template_invokes_shared_cli_contract() -> None:
    template = Path("ci/gitlab/uqo.gitlab-ci.yml").read_text(encoding="utf-8")
    assert 'UQO_ARGS=(run --config "$UQO_CONFIG_PATH" --ci)' in template
    assert "UQO_GHOST_MODE" in template
    assert "--stream-json" in template
    assert "--no-persist" in template
    assert "UQO_RUNNER_IMAGE" in template
    assert "UQO_RUNNER_PREBUILT" in template


def test_gitlab_template_defines_summary_artifacts() -> None:
    payload = yaml.safe_load(Path("ci/gitlab/uqo.gitlab-ci.yml").read_text(encoding="utf-8"))
    job = payload["uqo_run"]
    artifacts = job["artifacts"]
    assert "uqo-output.ndjson" in artifacts["paths"]
    assert "uqo-summary.json" in artifacts["paths"]
