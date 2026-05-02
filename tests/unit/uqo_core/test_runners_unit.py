"""Isolated tests for ``uqo_core.runners`` with mocked subprocess / I/O."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from uqo_core.command_builders import BuiltCommand, RunConfig, TestType
from uqo_core.runners import (
    DOCKER_MOUNT_POINT,
    ORCHESTRATOR_MOUNT_POINT,
    UQO_DONE_MARKER,
    _docker_volumes_for,
    _resolve_subprocess_argv,
    _rewrite_container_arg,
    _run_in_ephemeral_container_streaming,
    _to_container_path,
    run_streaming,
    validate_target_repo,
)


@pytest.fixture
def minimal_target_repo(tmp_path: Path) -> Path:
    return tmp_path


def test_resolve_subprocess_uses_shutil_which(monkeypatch: pytest.MonkeyPatch, minimal_target_repo: Path) -> None:
    called: dict[str, str] = {}

    def fake_which(name: str) -> str | None:
        called["which"] = name
        return f"/mock/bin/{name}"

    monkeypatch.setattr("uqo_core.runners.shutil.which", fake_which)
    argv = ["pytest", "-q"]
    _resolve_subprocess_argv(argv)
    assert called.get("which") == "pytest"
    assert argv[0] == "/mock/bin/pytest"


def test_run_streaming_uses_docker_execution_seam(minimal_target_repo: Path) -> None:
    cfg = RunConfig(
        test_type=TestType.PYTEST,
        target_repo=minimal_target_repo,
        shared_allure_results_dir=minimal_target_repo / "allure",
        pytest_args=("-q",),
    )

    captured: dict[str, object] = {}

    def fake_docker_run(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        kwargs["emit"]("stdout", "one line of output\n")
        return 0, 1.0, 2.0

    with patch("uqo_core.runners._run_in_ephemeral_container_streaming", side_effect=fake_docker_run):
        events: list[object] = []
        gen = run_streaming(cfg, prepare_allure=False, emit_done_marker=False, sync_static=False)
        for item in gen:
            events.append(item)

    assert captured["cmd"].cwd == minimal_target_repo.resolve()
    assert events


def test_validate_target_repo() -> None:
    assert validate_target_repo(Path("."))[0] is True


def test_uqo_done_marker_constant() -> None:
    assert isinstance(UQO_DONE_MARKER, str) and UQO_DONE_MARKER.startswith("[")


def test_docker_mapping_mounts_external_target_and_orchestrator(tmp_path: Path) -> None:
    target_repo = (tmp_path / "target").resolve()
    target_repo.mkdir()

    volumes = _docker_volumes_for(target_repo)

    assert volumes[str(target_repo)]["bind"] == DOCKER_MOUNT_POINT
    assert any(cfg["bind"] == ORCHESTRATOR_MOUNT_POINT for cfg in volumes.values())


def test_docker_mapping_rewrites_host_paths_for_container(tmp_path: Path) -> None:
    target_repo = (tmp_path / "target").resolve()
    target_repo.mkdir()
    allure_dir = target_repo / "artifacts" / "allure-results" / "pytest"
    repo_root = Path(__file__).resolve().parents[3]
    hook_arg = f"{target_repo / 'locustfile.py'},{repo_root / 'drop_in_hooks' / 'locust_custom' / 'locust_hooks.py'}"

    assert _to_container_path(allure_dir, target_root=target_repo) == "/app/artifacts/allure-results/pytest"
    assert _rewrite_container_arg(str(allure_dir), target_root=target_repo) == "/app/artifacts/allure-results/pytest"

    rewritten_hook_arg = _rewrite_container_arg(hook_arg, target_root=target_repo)
    assert rewritten_hook_arg.startswith("/app/locustfile.py,")
    assert f",{ORCHESTRATOR_MOUNT_POINT}/drop_in_hooks/locust_custom/locust_hooks.py" in rewritten_hook_arg


def test_local_subprocess_fallback_streams_stdout_stderr_and_writes_log(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("uqo_core.runners._docker_client", lambda: None)
    log_path = tmp_path / "logs" / "run.log"
    emitted: list[tuple[str, str]] = []
    cmd = BuiltCommand(
        argv=[
            sys.executable,
            "-c",
            "import sys; print('hello fallback'); print('stderr merged', file=sys.stderr)",
        ],
        cwd=tmp_path,
        env={},
    )

    rc, started_at, finished_at = _run_in_ephemeral_container_streaming(
        run_id="local-ok",
        cmd=cmd,
        cfg_timeout_s=5.0,
        cfg_heartbeat_s=0.0,
        emit=lambda stream, line: emitted.append((stream, line)),
        log_path=log_path,
    )

    assert rc == 0
    assert finished_at >= started_at
    assert ("stdout", "hello fallback\n") in emitted
    assert ("stdout", "stderr merged\n") in emitted
    assert any("docker unavailable" in line for stream, line in emitted if stream == "meta")
    assert set(log_path.read_text(encoding="utf-8").splitlines()) == {"hello fallback", "stderr merged"}


def test_local_subprocess_fallback_times_out_and_emits_124(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("uqo_core.runners._docker_client", lambda: None)
    events: list[tuple[str, str]] = []

    rc, _started_at, _finished_at = _run_in_ephemeral_container_streaming(
        run_id="rid-timeout",
        cmd=BuiltCommand(
            argv=[
                sys.executable,
                "-c",
                "import time; print('started', flush=True); time.sleep(10)",
            ],
            cwd=tmp_path,
            env={},
        ),
        cfg_timeout_s=0.2,
        cfg_heartbeat_s=0.0,
        emit=lambda stream, line: events.append((stream, line)),
        log_path=tmp_path / "logs" / "timeout.log",
    )

    assert rc == 124
    assert ("stdout", "started\n") in events
    assert any("timeout after 0.2s" in line for stream, line in events if stream == "meta")


def test_local_subprocess_fallback_reports_missing_executable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("uqo_core.runners._docker_client", lambda: None)
    monkeypatch.setattr("uqo_core.runners.shutil.which", lambda _name: None)
    monkeypatch.setattr("uqo_core.runners.sys.executable", "/missing/python")
    events: list[tuple[str, str]] = []

    rc, _started_at, _finished_at = _run_in_ephemeral_container_streaming(
        run_id="rid-missing",
        cmd=BuiltCommand(
            argv=["definitely-missing-uqo-command"],
            cwd=tmp_path,
            env={},
        ),
        cfg_timeout_s=5.0,
        cfg_heartbeat_s=0.0,
        emit=lambda stream, line: events.append((stream, line)),
        log_path=tmp_path / "logs" / "missing.log",
    )

    assert rc == 127
    assert any("[subprocess error]" in line for stream, line in events if stream == "meta")
