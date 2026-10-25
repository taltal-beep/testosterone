"""The failing tests of one run (testo_core/services/run_failures.py)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from testo_core.history.views import CompletedRunView
from testo_core.repository.models import RunStatus
from testo_core.services import run_failures


def _run(run_id: str, *, cycle: str = "unit", created_at: float = 1.0) -> CompletedRunView:
    return CompletedRunView(
        run_id=run_id,
        status=RunStatus.COMPLETED,
        created_at=created_at,
        started_at=created_at,
        finished_at=created_at + 1,
        test_kind="cycle",
        returncode=1,
        wall_duration_ms=1000.0,
        metrics_duration_ms=None,
        total_tests=None,
        passed=None,
        failed=None,
        broken=None,
        skipped=None,
        avg_case_ms=None,
        health_pct=None,
        target_repo=None,
        snapshot_dir=f"static/history/{run_id}/artifacts",
        audit_json=None,
        cycle=cycle,
    )


def _write(
    root: Path, run: CompletedRunView, results: dict[str, tuple[str, str]], stage: str = "api"
) -> None:
    folder = root / str(run.snapshot_dir) / stage / "allure-results" / "pytest"
    folder.mkdir(parents=True, exist_ok=True)
    for name, (status, message) in results.items():
        body = {"historyId": name, "name": name, "fullName": f"tests.m.{name}", "status": status}
        if message:
            body["statusDetails"] = {"message": message, "trace": "Traceback ..."}
        (folder / f"{name}-result.json").write_text(json.dumps(body), encoding="utf-8")


@pytest.fixture
def history(monkeypatch, tmp_path: Path):  # noqa: ANN001, ANN201
    """Four runs of ``unit`` (newest first) plus one of another cycle, wired into the service."""
    runs = [
        _run("r4", created_at=4),
        _run("other", cycle="nightly", created_at=3.5),
        _run("r3", created_at=3),
        _run("r2", created_at=2),
        _run("r1", created_at=1),
    ]
    by_id = {r.run_id: r for r in runs}
    monkeypatch.setattr(run_failures.paths, "ORCHESTRATOR_ROOT", tmp_path)
    monkeypatch.setattr(run_failures, "list_recent_runs", lambda *, limit: runs)
    monkeypatch.setattr(run_failures, "get_run", lambda *, run_id: by_id.get(run_id))
    return tmp_path, by_id


def test_failing_since_counts_the_streak_and_new_breakages_come_first(history) -> None:  # noqa: ANN001
    root, runs = history
    ok = ("passed", "")
    _write(root, runs["r1"], {"test_old": ok, "test_new": ok, "test_flaky": ok})
    _write(
        root,
        runs["r2"],
        {
            "test_old": ("failed", "AssertionError: 1 != 2"),
            "test_new": ok,
            "test_flaky": ("failed", "boom"),
        },
    )
    _write(
        root,
        runs["r3"],
        {"test_old": ("failed", "AssertionError: 1 != 2"), "test_new": ok, "test_flaky": ok},
    )
    _write(
        root,
        runs["r4"],
        {
            "test_old": ("failed", "AssertionError: 1 != 3"),
            "test_new": ("broken", "KeyError: 'id'\nmore"),
            "test_flaky": ("failed", "boom"),
        },
    )
    # Another cycle's run never counts.
    _write(root, runs["other"], {"test_old": ok})

    result = run_failures.load_run_failures("r4")

    assert result is not None
    assert [t.name for t in result.tests] == ["test_flaky", "test_new", "test_old"]
    by_name = {t.name: t for t in result.tests}
    assert (by_name["test_old"].failing_runs, by_name["test_old"].failing_since_run_id) == (3, "r2")
    assert (by_name["test_new"].failing_runs, by_name["test_new"].failing_since_run_id) == (1, "r4")
    assert by_name["test_new"].message == "KeyError: 'id'"
    assert by_name["test_new"].stage == "api"
    assert by_name["test_flaky"].flaky and not by_name["test_old"].flaky
    assert result.new_failures == 2
    assert result.runs_considered == 4


def test_failures_with_the_same_message_are_grouped(history) -> None:  # noqa: ANN001
    root, runs = history
    refused = "ConnectionRefusedError: [Errno 111] Connection refused to 'localhost:8001'"
    _write(
        root,
        runs["r4"],
        {
            "test_a": ("failed", refused),
            "test_b": ("failed", refused.replace("8001", "8002")),
            "test_c": ("failed", "AssertionError"),
            "test_d": ("passed", ""),
        },
    )

    result = run_failures.load_run_failures("r4")

    assert result is not None
    assert len(result.tests) == 3
    assert len(result.groups) == 1
    assert result.groups[0].count == 2
    assert set(result.groups[0].keys) == {"test_a", "test_b"}


def test_a_green_run_has_no_failures(history) -> None:  # noqa: ANN001
    root, runs = history
    _write(root, runs["r4"], {"test_a": ("passed", "")})
    result = run_failures.load_run_failures("r4")
    assert result is not None
    assert (result.tests, result.groups, result.new_failures) == ((), (), 0)


def test_unknown_run_is_none(history) -> None:  # noqa: ANN001
    assert run_failures.load_run_failures("nope") is None


def test_a_pull_request_is_judged_against_its_target_branch(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    # Newest first: the PR's run, a parallel PR, main, then the PR's earlier run.
    pr = replace(_run("pr2", created_at=4), branch="feat", base_branch="main")
    other_pr = replace(_run("x1", created_at=3), branch="other", base_branch="main")
    main = replace(_run("m1", created_at=2), branch="main")
    pr_before = replace(_run("pr1", created_at=1), branch="feat", base_branch="main")
    runs = [pr, other_pr, main, pr_before]
    monkeypatch.setattr(run_failures.paths, "ORCHESTRATOR_ROOT", tmp_path)
    monkeypatch.setattr(run_failures, "list_recent_runs", lambda *, limit: runs)
    monkeypatch.setattr(run_failures, "get_run", lambda *, run_id: pr if run_id == "pr2" else None)
    fail, ok = ("failed", "boom"), ("passed", "")
    _write(tmp_path, pr, {"test_broken_on_main": fail, "test_mine": fail, "test_since_pr1": fail})
    _write(
        tmp_path, other_pr, {"test_broken_on_main": fail, "test_mine": fail, "test_since_pr1": fail}
    )
    _write(tmp_path, main, {"test_broken_on_main": fail, "test_mine": ok, "test_since_pr1": ok})
    _write(
        tmp_path, pr_before, {"test_broken_on_main": ok, "test_mine": ok, "test_since_pr1": fail}
    )

    found = run_failures.load_run_failures("pr2")

    assert found is not None
    assert (found.baseline_run_id, found.baseline_branch) == ("m1", "main")
    tests = {t.name: t for t in found.tests}
    assert not tests["test_broken_on_main"].new  # main has it too
    assert tests["test_mine"].new
    assert tests["test_since_pr1"].new  # passing on main, so this PR broke it
    # Streaks follow the PR's own branch: the parallel PR's failure doesn't count.
    assert tests["test_mine"].failing_runs == 1
    assert tests["test_since_pr1"].failing_runs == 2
    assert found.new_failures == 2


def test_without_branches_new_means_not_failing_in_the_run_before(history) -> None:  # noqa: ANN001
    root, runs = history
    _write(root, runs["r3"], {"test_a": ("failed", "x"), "test_b": ("passed", "")})
    _write(root, runs["r4"], {"test_a": ("failed", "x"), "test_b": ("failed", "y")})

    found = run_failures.load_run_failures("r4")

    assert found is not None
    assert found.baseline_run_id == "r3" and found.baseline_branch is None
    assert {t.name: t.new for t in found.tests} == {"test_a": False, "test_b": True}


def test_message_signature_ignores_numbers_and_quoted_values() -> None:
    assert run_failures.message_signature(
        "Timeout after 30.5s on 'a'"
    ) == run_failures.message_signature("Timeout after 12s on 'b'")
    assert run_failures.message_signature("KeyError") != run_failures.message_signature(
        "ValueError"
    )
