from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


def _load_wrapper_module():
    script = Path("integrations/github-action/run_uqo_action.py").resolve()
    spec = importlib.util.spec_from_file_location("run_uqo_action", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_command_includes_expected_flags() -> None:
    module = _load_wrapper_module()
    cmd = module.build_command(
        config_path="config.yml",
        ci_mode=True,
        stream_json=True,
        persist=False,
        ghost_mode="true",
    )
    assert cmd == ["uqo", "run", "--config", "config.yml", "--ci", "--ghost", "--stream-json", "--no-persist"]


def test_extract_summary_uses_last_summary_json_line() -> None:
    module = _load_wrapper_module()
    stdout = "\n".join(
        [
            '{"event":"log","line":"hello"}',
            '{"schema_version":"1","exit_code":0,"runs":[{"run_id":"rid-1"}]}',
        ]
    )
    summary = module._extract_summary(stdout, fallback_exit_code=4)
    assert summary["exit_code"] == 0
    assert summary["runs"][0]["run_id"] == "rid-1"


def test_parse_runner_prebuilt_normalizes_values() -> None:
    module = _load_wrapper_module()
    assert module._parse_runner_prebuilt("true") == "true"
    assert module._parse_runner_prebuilt("FALSE") == "false"
    assert module._parse_runner_prebuilt("invalid") == "auto"


def test_main_writes_outputs_and_summary_file(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    module = _load_wrapper_module()
    summary_payload = {"schema_version": "1", "exit_code": 0, "runs": [{"run_id": "rid-7"}]}
    fake_stdout = json.dumps(summary_payload) + "\n"
    captured_env: dict[str, str] = {}

    def fake_run(*_args, **kwargs):  # noqa: ANN001
        env = kwargs.get("env")
        if isinstance(env, dict):
            captured_env.update({k: str(v) for k, v in env.items()})
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=fake_stdout, stderr="")

    output_file = tmp_path / "github_output.txt"
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))

    code = module.main(
        [
            "--config-path",
            "config.yml",
            "--ci-mode",
            "true",
            "--ghost-mode",
            "auto",
            "--stream-json",
            "false",
            "--persist",
            "true",
            "--runner-image",
            "docker.io/acme/uqo-runner:v1",
            "--runner-prebuilt",
            "true",
        ]
    )
    assert code == 0

    lines = output_file.read_text(encoding="utf-8").splitlines()
    kv = dict(line.split("=", 1) for line in lines if "=" in line)
    assert kv["exit_code"] == "0"
    assert kv["run_id"] == "rid-7"
    assert kv["status"] == "success"
    summary_path = Path(kv["summary_path"])
    assert summary_path.is_file()
    assert captured_env["UQO_RUNNER_IMAGE"] == "docker.io/acme/uqo-runner:v1"
    assert captured_env["UQO_RUNNER_PREBUILT"] == "true"
