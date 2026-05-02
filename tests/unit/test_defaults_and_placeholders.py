"""Coverage for small defaults and placeholder runners."""

from __future__ import annotations

from pathlib import Path

from uqo_core.report_generator import ReportServer, default_report_paths, url_for
from unittest.mock import patch

from uqo_core.runners import LogEvent, RunResult, run_native_behave


def test_default_report_paths_points_to_static(tmp_path: Path) -> None:
    p = default_report_paths(artifacts_root=tmp_path)
    assert p.results_dir == tmp_path / "allure-results"
    # output is always the static allure dir (not under artifacts)
    assert "static" in str(p.report_dir)


def test_url_for_formats_relative_path(tmp_path: Path) -> None:
    # Minimal ReportServer stub
    srv = ReportServer(port=1234, root_dir=tmp_path, thread=None, httpd=None)  # type: ignore[arg-type]
    u = url_for(srv, relative_path="/x/y.html")
    assert u.endswith("/x/y.html")


def test_run_native_behave_emits_and_returns(tmp_path: Path) -> None:
    (tmp_path / "features").mkdir()

    def fake_docker_run(**kwargs):  # type: ignore[no-untyped-def]
        kwargs["emit"]("stdout", "ok\n")
        return 0, 1.0, 2.0

    with patch("uqo_core.runners._run_in_ephemeral_container_streaming", side_effect=fake_docker_run):
        gen = run_native_behave(target_repo=tmp_path, artifacts_root=tmp_path)
        ev = next(gen)
        assert isinstance(ev, LogEvent)
        try:
            while True:
                next(gen)
        except StopIteration as e:
            rr = e.value
    assert isinstance(rr, RunResult)
    assert rr.returncode == 0

