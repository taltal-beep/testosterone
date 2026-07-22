from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from testo_core.command_builders import BuiltCommand, TestType
from testo_core.runners import LogEvent, RunResult
from testo_core.services.ci_provenance import CIProvenance
from testo_core.services.headless_engine import (
    ConfigValidationError,
    EngineEvent,
    EngineRunRecord,
    EngineRunSpec,
    EngineSummary,
    InfrastructureRuntimeError,
)


def _summary(*, exit_code: int = 0) -> EngineSummary:
    return EngineSummary(
        schema_version="1",
        trigger_source="ci",
        ci_mode=True,
        persist=True,
        exit_code=exit_code,
        aggregate_returncode=0 if exit_code == 0 else 1,
        started_at=time.time() - 1.0,
        finished_at=time.time(),
        runs=(
            EngineRunRecord(
                test_type=TestType.PYTEST.value,
                run_id="rid-1",
                returncode=0,
                started_at=time.time() - 1.0,
                finished_at=time.time(),
                duration_s=1.0,
                cwd="/tmp/repo",
            ),
        ),
        error=None,
    )


def test_cli_invalid_config_returns_exit_2(monkeypatch, capsys) -> None:  # noqa: ANN001
    from testo_core import cli

    def fake_load(_path: Path):  # noqa: ANN001
        raise ConfigValidationError("bad config")

    monkeypatch.setattr(cli, "load_run_specs_from_yaml", fake_load)
    code = cli.main(["run", "--config", "missing.yaml", "--ci"])
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)

    assert code == 2
    assert payload["exit_code"] == 2
    assert "bad config" in payload["error"]


def test_cli_ci_json_summary(monkeypatch, capsys, tmp_path: Path) -> None:  # noqa: ANN001
    from testo_core import cli

    target = tmp_path / "repo"
    target.mkdir()

    monkeypatch.setattr(
        cli,
        "load_run_specs_from_yaml",
        lambda _path: (EngineRunSpec(test_type=TestType.PYTEST, target_repo=target),),
    )

    class FakeEngine:
        def stream(self, request):  # noqa: ANN001
            del request
            if False:
                yield
            return _summary(exit_code=0)

    monkeypatch.setattr(cli, "HeadlessEngineService", FakeEngine)
    code = cli.main(["run", "--config", "ok.yaml", "--ci", "--json"])
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)

    assert code == 0
    assert payload["exit_code"] == 0
    assert payload["trigger_source"] == "ci"


def test_cli_ci_sets_request_trigger_source_and_provenance(monkeypatch, capsys, tmp_path: Path) -> None:  # noqa: ANN001
    from testo_core import cli

    target = tmp_path / "repo"
    target.mkdir()
    monkeypatch.setattr(
        cli,
        "load_run_specs_from_yaml",
        lambda _path: (EngineRunSpec(test_type=TestType.PYTEST, target_repo=target),),
    )
    monkeypatch.setattr(
        cli,
        "detect_ci_provenance",
        lambda _env: CIProvenance(ci_provider="github", ci_pipeline_id="123"),
    )

    captured_requests: list = []

    class FakeEngine:
        def stream(self, request):  # noqa: ANN001
            captured_requests.append(request)
            if False:
                yield
            return _summary(exit_code=0)

    monkeypatch.setattr(cli, "HeadlessEngineService", FakeEngine)
    code = cli.main(["run", "--config", "ok.yaml", "--ci"])
    payload = json.loads(capsys.readouterr().out.strip())

    assert code == 0
    assert payload["exit_code"] == 0
    assert captured_requests[0].trigger_source == "ci"
    assert captured_requests[0].provenance == CIProvenance(ci_provider="github", ci_pipeline_id="123")


def test_cli_auto_detects_ci_env_without_ci_flag(monkeypatch, capsys, tmp_path: Path) -> None:  # noqa: ANN001
    from testo_core import cli

    target = tmp_path / "repo"
    target.mkdir()
    monkeypatch.setattr(
        cli,
        "load_run_specs_from_yaml",
        lambda _path: (EngineRunSpec(test_type=TestType.PYTEST, target_repo=target),),
    )
    monkeypatch.setattr(cli.os, "environ", {"GITHUB_ACTIONS": "true", "GITHUB_RUN_ID": "321"})

    captured_requests: list = []

    class FakeEngine:
        def stream(self, request):  # noqa: ANN001
            captured_requests.append(request)
            if False:
                yield
            return _summary(exit_code=0)

    monkeypatch.setattr(cli, "HeadlessEngineService", FakeEngine)
    code = cli.main(["run", "--config", "ok.yaml"])
    payload = json.loads(capsys.readouterr().out.strip())

    assert code == 0
    assert payload["trigger_source"] == "ci"
    assert captured_requests[0].ci_mode is True
    assert captured_requests[0].provenance == CIProvenance(ci_provider="github", ci_pipeline_id="321")


def test_cli_no_ghost_overrides_ci_env(monkeypatch, capsys, tmp_path: Path) -> None:  # noqa: ANN001
    from testo_core import cli

    target = tmp_path / "repo"
    target.mkdir()
    monkeypatch.setattr(
        cli,
        "load_run_specs_from_yaml",
        lambda _path: (EngineRunSpec(test_type=TestType.PYTEST, target_repo=target),),
    )
    monkeypatch.setattr(cli.os, "environ", {"GITHUB_ACTIONS": "true"})

    captured_requests: list = []

    class FakeEngine:
        def stream(self, request):  # noqa: ANN001
            captured_requests.append(request)
            if False:
                yield
            return _summary(exit_code=0)

    monkeypatch.setattr(cli, "HeadlessEngineService", FakeEngine)
    code = cli.main(["run", "--config", "ok.yaml", "--no-ghost"])
    _ = json.loads(capsys.readouterr().out.strip())

    assert code == 0
    assert captured_requests[0].ci_mode is False
    assert captured_requests[0].trigger_source == "cli"
    assert captured_requests[0].provenance is None


def test_cli_ghost_forces_ci_mode(monkeypatch, capsys, tmp_path: Path) -> None:  # noqa: ANN001
    from testo_core import cli

    target = tmp_path / "repo"
    target.mkdir()
    monkeypatch.setattr(
        cli,
        "load_run_specs_from_yaml",
        lambda _path: (EngineRunSpec(test_type=TestType.PYTEST, target_repo=target),),
    )
    monkeypatch.setattr(cli.os, "environ", {})

    captured_requests: list = []

    class FakeEngine:
        def stream(self, request):  # noqa: ANN001
            captured_requests.append(request)
            if False:
                yield
            return _summary(exit_code=0)

    monkeypatch.setattr(cli, "HeadlessEngineService", FakeEngine)
    code = cli.main(["run", "--config", "ok.yaml", "--ghost"])
    payload = json.loads(capsys.readouterr().out.strip())

    assert code == 0
    assert payload["trigger_source"] == "ci"
    assert captured_requests[0].ci_mode is True
    assert captured_requests[0].trigger_source == "ci"


def test_cli_stream_json_outputs_ndjson(monkeypatch, capsys, tmp_path: Path) -> None:  # noqa: ANN001
    from testo_core import cli

    target = tmp_path / "repo"
    target.mkdir()

    monkeypatch.setattr(
        cli,
        "load_run_specs_from_yaml",
        lambda _path: (EngineRunSpec(test_type=TestType.PYTEST, target_repo=target),),
    )

    cmd = BuiltCommand(
        argv=["pytest", "-q"],
        cwd=target,
        env={"UQO_RUN_ID": "rid-1", "UQO_LAST_TEST_TYPE": "pytest"},
    )
    rr = RunResult(returncode=0, started_at=time.time() - 1, finished_at=time.time(), command=cmd)

    class FakeEngine:
        def stream(self, request):  # noqa: ANN001
            del request
            yield EngineEvent(kind="log", payload=LogEvent(ts=time.time(), stream="stdout", line="line\n"))
            yield EngineEvent(kind="run_result", payload=rr)
            return _summary(exit_code=0)

    monkeypatch.setattr(cli, "HeadlessEngineService", FakeEngine)
    code = cli.main(["run", "--config", "ok.yaml", "--ci", "--stream-json"])
    out_lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]

    assert code == 0
    assert len(out_lines) == 3
    first = json.loads(out_lines[0])
    last = json.loads(out_lines[-1])
    assert first["event"] == "log"
    assert last["exit_code"] == 0


def test_cli_stream_json_always_emits_final_summary(monkeypatch, capsys, tmp_path: Path) -> None:  # noqa: ANN001
    from testo_core import cli

    target = tmp_path / "repo"
    target.mkdir()

    monkeypatch.setattr(
        cli,
        "load_run_specs_from_yaml",
        lambda _path: (EngineRunSpec(test_type=TestType.PYTEST, target_repo=target),),
    )

    cmd = BuiltCommand(
        argv=["pytest", "-q"],
        cwd=target,
        env={"UQO_RUN_ID": "rid-1", "UQO_LAST_TEST_TYPE": "pytest"},
    )
    rr = RunResult(returncode=0, started_at=time.time() - 1, finished_at=time.time(), command=cmd)

    class FakeEngine:
        def stream(self, request):  # noqa: ANN001
            del request
            yield EngineEvent(kind="run_result", payload=rr)
            return _summary(exit_code=0)

    monkeypatch.setattr(cli, "HeadlessEngineService", FakeEngine)
    code = cli.main(["run", "--config", "ok.yaml", "--stream-json"])
    out_lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    summary = json.loads(out_lines[-1])

    assert code == 0
    assert summary["schema_version"] == "1"
    assert summary["exit_code"] == 0


def test_cli_ci_mode_keeps_stderr_clean(monkeypatch, capsys, tmp_path: Path) -> None:  # noqa: ANN001
    from testo_core import cli

    target = tmp_path / "repo"
    target.mkdir()

    monkeypatch.setattr(
        cli,
        "load_run_specs_from_yaml",
        lambda _path: (EngineRunSpec(test_type=TestType.PYTEST, target_repo=target),),
    )

    class FakeEngine:
        def stream(self, request):  # noqa: ANN001
            del request
            yield EngineEvent(kind="log", payload=LogEvent(ts=time.time(), stream="stdout", line="human line\n"))
            return _summary(exit_code=0)

    monkeypatch.setattr(cli, "HeadlessEngineService", FakeEngine)
    code = cli.main(["run", "--config", "ok.yaml", "--ci"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip())

    assert code == 0
    assert payload["exit_code"] == 0
    assert captured.err == ""


@pytest.mark.parametrize("exit_code", [0, 1, 3, 4])
def test_cli_passes_through_engine_exit_codes(monkeypatch, capsys, tmp_path: Path, exit_code: int) -> None:  # noqa: ANN001
    from testo_core import cli

    target = tmp_path / "repo"
    target.mkdir()

    monkeypatch.setattr(
        cli,
        "load_run_specs_from_yaml",
        lambda _path: (EngineRunSpec(test_type=TestType.PYTEST, target_repo=target),),
    )

    class FakeEngine:
        def stream(self, request):  # noqa: ANN001
            del request
            if False:
                yield
            return _summary(exit_code=exit_code)

    monkeypatch.setattr(cli, "HeadlessEngineService", FakeEngine)
    code = cli.main(["run", "--config", "ok.yaml", "--ci", "--json"])
    payload = json.loads(capsys.readouterr().out.strip())

    assert code == exit_code
    assert payload["exit_code"] == exit_code


def test_cli_unhandled_exception_maps_to_exit_4(monkeypatch, capsys, tmp_path: Path) -> None:  # noqa: ANN001
    from testo_core import cli

    target = tmp_path / "repo"
    target.mkdir()
    monkeypatch.setattr(
        cli,
        "load_run_specs_from_yaml",
        lambda _path: (EngineRunSpec(test_type=TestType.PYTEST, target_repo=target),),
    )

    class FakeEngine:
        def stream(self, request):  # noqa: ANN001
            del request
            raise RuntimeError("boom")
            yield  # pragma: no cover

    monkeypatch.setattr(cli, "HeadlessEngineService", FakeEngine)
    code = cli.main(["run", "--config", "ok.yaml", "--ci", "--json"])
    payload = json.loads(capsys.readouterr().out.strip())

    assert code == 4
    assert payload["exit_code"] == 4


def test_cli_headless_engine_error_preserves_exit_code(monkeypatch, capsys, tmp_path: Path) -> None:  # noqa: ANN001
    from testo_core import cli

    target = tmp_path / "repo"
    target.mkdir()
    monkeypatch.setattr(
        cli,
        "load_run_specs_from_yaml",
        lambda _path: (EngineRunSpec(test_type=TestType.PYTEST, target_repo=target),),
    )

    class FakeEngine:
        def stream(self, request):  # noqa: ANN001
            del request
            raise InfrastructureRuntimeError("infra down")
            yield  # pragma: no cover

    monkeypatch.setattr(cli, "HeadlessEngineService", FakeEngine)
    code = cli.main(["run", "--config", "ok.yaml", "--ci"])
    payload = json.loads(capsys.readouterr().out.strip())

    assert code == 3
    assert payload["exit_code"] == 3


def test_cli_rejects_conflicting_ghost_flags(capsys) -> None:  # noqa: ANN001
    from testo_core import cli

    with pytest.raises(SystemExit) as exc:
        cli.main(["run", "--config", "ok.yaml", "--ghost", "--no-ghost"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "--no-ghost" in err
