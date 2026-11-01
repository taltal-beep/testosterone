from __future__ import annotations

from pathlib import Path

import yaml


def test_github_fast_workflow_has_required_gate_command() -> None:
    # The fast-required gate now lives in the consolidated `ci.yml` pipeline
    # (test job), which replaced the standalone pr-fast.yml workflow.
    payload = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
    job = payload["jobs"]["test"]
    runs = [step.get("run", "") for step in job["steps"] if isinstance(step, dict)]
    fast = [r for r in runs if '-m "tier_fast and not quarantined"' in r]
    assert len(fast) == 1
    assert 'python -m pytest -q -m "tier_fast and not quarantined" --maxfail=1' in fast[0]
    # The coverage gate in pytest.ini must stay active on the fast suite.
    assert "--no-cov" not in fast[0]


def test_github_test_job_also_runs_the_heavy_tier() -> None:
    payload = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
    runs = "\n".join(step.get("run", "") for step in payload["jobs"]["test"]["steps"])
    assert '-m "tier_heavy and not tier_external and not quarantined"' in runs


def test_github_heavy_workflow_is_manual_or_label_triggered() -> None:
    payload = yaml.safe_load(Path(".github/workflows/pr-heavy.yml").read_text(encoding="utf-8"))
    on_section = payload.get("on") or payload.get(True) or {}
    assert "workflow_dispatch" in on_section
    assert payload["jobs"]["heavy_optional"]["if"]


def test_github_external_workflows_use_external_marker_command() -> None:
    nightly = yaml.safe_load(
        Path(".github/workflows/nightly-external.yml").read_text(encoding="utf-8")
    )
    release = yaml.safe_load(Path(".github/workflows/release-gate.yml").read_text(encoding="utf-8"))
    nightly_commands = "\n".join(
        step.get("run", "")
        for step in nightly["jobs"]["external_nightly"]["steps"]
        if isinstance(step, dict)
    )
    release_commands = "\n".join(
        step.get("run", "")
        for step in release["jobs"]["external_release_gate"]["steps"]
        if isinstance(step, dict)
    )
    marker_cmd = (
        'python -m pytest -q -m "tier_external and cleanup_required" --maxfail=1 --durations=50'
    )
    assert marker_cmd in nightly_commands
    assert marker_cmd in release_commands
    # A marker subset can't meet pytest.ini's project-wide coverage gate.
    assert "--no-cov" in nightly_commands
    assert "--no-cov" in release_commands
