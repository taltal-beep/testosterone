from __future__ import annotations

from pathlib import Path

import yaml


def test_github_fast_workflow_has_required_gate_command() -> None:
    # The fast-required gate now lives in the consolidated `ci.yml` pipeline
    # (test job), which replaced the standalone pr-fast.yml workflow.
    payload = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
    job = payload["jobs"]["test"]
    commands = "\n".join(step.get("run", "") for step in job["steps"] if isinstance(step, dict))
    assert 'python -m pytest -q -m "tier_fast and not quarantined" --maxfail=1 --no-cov' in commands


def test_github_heavy_workflow_is_manual_or_label_triggered() -> None:
    payload = yaml.safe_load(Path(".github/workflows/pr-heavy.yml").read_text(encoding="utf-8"))
    on_section = payload.get("on") or payload.get(True) or {}
    assert "workflow_dispatch" in on_section
    assert payload["jobs"]["heavy_optional"]["if"]


def test_github_external_workflows_use_external_marker_command() -> None:
    nightly = yaml.safe_load(Path(".github/workflows/nightly-external.yml").read_text(encoding="utf-8"))
    release = yaml.safe_load(Path(".github/workflows/release-gate.yml").read_text(encoding="utf-8"))
    nightly_commands = "\n".join(step.get("run", "") for step in nightly["jobs"]["external_nightly"]["steps"] if isinstance(step, dict))
    release_commands = "\n".join(step.get("run", "") for step in release["jobs"]["external_release_gate"]["steps"] if isinstance(step, dict))
    marker_cmd = 'python -m pytest -q -m "tier_external and cleanup_required" --maxfail=1 --durations=50'
    assert marker_cmd in nightly_commands
    assert marker_cmd in release_commands


def test_gitlab_tier_templates_have_expected_jobs_and_artifacts() -> None:
    tiered = yaml.safe_load(Path("ci/gitlab/testo.tests.gitlab-ci.yml").read_text(encoding="utf-8"))
    external = yaml.safe_load(Path("ci/gitlab/testo.external.gitlab-ci.yml").read_text(encoding="utf-8"))
    assert "fast_required" in tiered
    assert "heavy_optional" in tiered
    assert "external_nightly" in external
    assert ".artifacts/e2e/" in tiered["fast_required"]["artifacts"]["paths"]
    assert ".artifacts/e2e/" in external["external_nightly"]["artifacts"]["paths"]

