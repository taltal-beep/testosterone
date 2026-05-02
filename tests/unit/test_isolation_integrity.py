"""
Isolation integrity tests.

These tests intentionally codify the SOLID firewall requirements:
  - No path overrides: runners must honor the explicit framework results directory.
  - No unified reporting: Allure HTML generation must be framework-scoped.
  - Streaming: native Behave must stream output incrementally (Popen-based).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uqo_core.command_builders import BuiltCommand, RunConfig, TestType
from uqo_core.runners import LogEvent, RunResult, run_audit_streaming, run_native_behave, run_streaming


def test_run_streaming_does_not_override_shared_allure_results_dir(tmp_path: Path) -> None:
    """
    When the UI passes a framework-scoped Allure results directory, the runner must
    isolate the subprocess under the run id instead of replacing it with a generic
    artifacts/allure-results root or mutating the shared framework parent.
    """

    requested = tmp_path / "artifacts" / "allure-results" / "pytest"
    requested.mkdir(parents=True, exist_ok=True)
    run_id = "rid-iso"

    cfg = RunConfig(
        test_type=TestType.PYTEST,
        target_repo=tmp_path,
        shared_allure_results_dir=requested,
        pytest_args=("-q",),
        run_id=run_id,
    )

    captured: dict[str, Path] = {}

    def fake_build_command(passed_cfg: RunConfig, *, parent_env) -> BuiltCommand:  # type: ignore[no-untyped-def]
        captured["shared"] = passed_cfg.shared_allure_results_dir
        return BuiltCommand(argv=["pytest", "-q"], cwd=tmp_path, env=dict(parent_env))

    with patch("uqo_core.runners.build_command", side_effect=fake_build_command):
        with patch("uqo_core.runners._run_in_ephemeral_container_streaming") as run:
            run.return_value = (0, 1.0, 2.0)
            list(
                run_streaming(
                    cfg,
                    artifacts_root=tmp_path / "artifacts",
                    # default prepare_allure=True is the historically buggy path
                    emit_done_marker=False,
                    sync_static=False,
                    run_framework_hooks=False,
                )
            )

    assert captured.get("shared") == requested / run_id


def test_audit_does_not_generate_unified_allure_html(tmp_path: Path) -> None:
    """
    Audit must not generate a unified Allure report from the parent results dir.
    It must generate per-framework HTML under static/allure_reports/{framework}/.
    """

    mock_rr = RunResult(
        returncode=0,
        started_at=0.0,
        finished_at=1.0,
        command=BuiltCommand(argv=["x"], cwd=tmp_path, env={}),
    )

    def fake_run_streaming(*_a, **_kw):
        yield LogEvent(ts=0.0, stream="meta", line="ping\n")
        return mock_rr

    calls: list[Path] = []

    def spy_generate_allure_html(*, results_dir: Path, report_dir: Path, **_kw):  # type: ignore[no-untyped-def]
        calls.append(results_dir)
        return True, "ok", 100.0

    with patch("uqo_core.runners.run_streaming", side_effect=fake_run_streaming):
        with patch("uqo_core.runners.generate_allure_html", side_effect=spy_generate_allure_html):
            with patch("uqo_core.runners.sync_all_reports_to_static", return_value={}):
                with patch("uqo_core.runners.collect_behavex_native_report", return_value=None):
                    with patch("uqo_core.runners.publish_locust_html_to_static", return_value=None):
                        gen = run_audit_streaming(target_repo=tmp_path, artifacts_root=tmp_path / "artifacts")
                        with pytest.raises(StopIteration):
                            while True:
                                next(gen)

    assert calls, "expected Allure generation calls"
    # No call may target the parent unified directory itself.
    assert all(p.name in {"pytest", "behavex", "locust", "behave_native"} for p in calls)


def test_run_native_behave_streams_container_output(tmp_path: Path) -> None:
    """
    Native Behave must yield runner output incrementally from the Docker execution seam;
    blocking until completion would look like a hang in the UI.
    """

    (tmp_path / "features").mkdir()

    def fake_docker_run(**kwargs):  # type: ignore[no-untyped-def]
        kwargs["emit"]("stdout", "line1\n")
        kwargs["emit"]("stdout", "line2\n")
        return 0, 0.0, 1.0

    seen: list[str] = []
    with patch("uqo_core.runners._run_in_ephemeral_container_streaming", side_effect=fake_docker_run) as docker_run:
        gen = run_native_behave(target_repo=tmp_path, artifacts_root=tmp_path / "artifacts")
        try:
            while True:
                seen.append(next(gen).line)
        except StopIteration:
            pass

    assert docker_run.called is True
    assert any("line1" in line for line in seen)
    assert any("line2" in line for line in seen)

