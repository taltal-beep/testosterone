"""Exercise ``run_audit_streaming`` with mocked phase runners."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from uqo_core.command_builders import BuiltCommand
from uqo_core.runners import LogEvent, RunResult, run_audit_streaming


def test_run_audit_streaming_with_mocked_phases(tmp_path: Path) -> None:
    mock_rr = RunResult(
        returncode=0,
        started_at=0.0,
        finished_at=1.0,
        command=BuiltCommand(argv=["x"], cwd=tmp_path, env={}),
    )

    def fake_run_streaming(*_a, **_kw):
        yield LogEvent(ts=0.0, stream="meta", line="ping\n")
        return mock_rr

    with patch("uqo_core.runners.run_streaming", side_effect=fake_run_streaming):
        with patch("uqo_core.runners.generate_allure_html", return_value=(True, "ok", 100.0)):
            with patch("uqo_core.runners.sync_all_reports_to_static", return_value={}):
                with patch("uqo_core.runners.collect_behavex_native_report", return_value=None):
                    with patch("uqo_core.runners.publish_locust_html_to_static", return_value=None):
                        gen = run_audit_streaming(target_repo=tmp_path, artifacts_root=tmp_path)
                        rr = None
                        try:
                            while True:
                                next(gen)
                        except StopIteration as e:
                            rr = e.value
                        assert isinstance(rr, RunResult)
                        assert rr.audit_mode is True
