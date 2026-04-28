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

from engine.command_builders import BuiltCommand, RunConfig, TestType
from engine.runners import LogEvent, RunResult, run_audit_streaming, run_native_behave, run_streaming


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

    class _Stdout:
        _lines = ["done\n"]

        def readline(self) -> str:
            return self._lines.pop(0) if self._lines else ""

    with patch("engine.runners.build_command", side_effect=fake_build_command):
        with patch("engine.runners.subprocess.Popen") as popen:
            proc = MagicMock()
            proc.stdout = _Stdout()
            proc.poll.side_effect = [None, 0]
            proc.wait.return_value = 0
            popen.return_value = proc

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

    with patch("engine.runners.run_streaming", side_effect=fake_run_streaming):
        with patch("engine.runners.generate_allure_html", side_effect=spy_generate_allure_html):
            with patch("engine.runners.sync_all_reports_to_static", return_value={}):
                with patch("engine.runners.collect_behavex_native_report", return_value=None):
                    with patch("engine.runners.publish_locust_html_to_static", return_value=None):
                        gen = run_audit_streaming(target_repo=tmp_path, artifacts_root=tmp_path / "artifacts")
                        with pytest.raises(StopIteration):
                            while True:
                                next(gen)

    assert calls, "expected Allure generation calls"
    # No call may target the parent unified directory itself.
    assert all(p.name in {"pytest", "behavex", "locust", "behave_native"} for p in calls)


def test_run_native_behave_uses_popen_for_streaming(tmp_path: Path) -> None:
    """
    Native Behave must be Popen-based so logs can stream; subprocess.run(capture_output=True)
    blocks the event stream and looks like a hang in the UI.
    """

    (tmp_path / "features").mkdir()

    with patch("engine.runners.subprocess.Popen") as popen:
        class _Stdout:
            _lines = ["line1\n", "line2\n"]

            def readline(self) -> str:
                return self._lines.pop(0) if self._lines else ""

        proc = MagicMock()
        proc.stdout = _Stdout()
        proc.poll.side_effect = [None, 0]
        proc.wait.return_value = 0
        popen.return_value = proc

        gen = run_native_behave(target_repo=tmp_path, artifacts_root=tmp_path / "artifacts")
        # Drain; implementation should call Popen during execution.
        try:
            while True:
                next(gen)
        except StopIteration:
            pass

    assert popen.called is True

