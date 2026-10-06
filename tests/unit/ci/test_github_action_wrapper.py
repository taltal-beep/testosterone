from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


def _load_wrapper_module():
    script = Path("integrations/github-action/run_testo_action.py").resolve()
    spec = importlib.util.spec_from_file_location("run_testo_action", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_command_includes_expected_flags() -> None:
    module = _load_wrapper_module()
    cmd = module.build_command(config_path="config.yml", cycle="smoke", ci_mode=True, persist=False)
    assert cmd == ["testo", "run", "--config", "config.yml", "--cycle", "smoke", "--ci", "--no-persist"]


def test_build_command_omits_empty_config_and_cycle() -> None:
    module = _load_wrapper_module()
    assert module.build_command(config_path="", cycle="", ci_mode=True, persist=True) == ["testo", "run", "--ci"]


def test_extract_summary_uses_last_plan_finished_line() -> None:
    module = _load_wrapper_module()
    stdout = "\n".join(
        [
            '{"event":"plan_started","plan":"smoke","stage_count":1}',
            '{"event":"stage_finished","stage":"s","returncode":0}',
            '{"event":"plan_finished","plan":"smoke","exit_code":0,"aggregate_returncode":0}',
        ]
    )
    summary = module._extract_summary(stdout, fallback_exit_code=4)
    assert summary["event"] == "plan_finished"
    assert summary["exit_code"] == 0


def test_extract_summary_falls_back_to_process_exit_code() -> None:
    module = _load_wrapper_module()
    summary = module._extract_summary("not json\n", fallback_exit_code=2)
    assert summary["event"] == "error"
    assert summary["exit_code"] == 2


def test_main_writes_outputs_and_summary_file(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    module = _load_wrapper_module()
    plan_finished = {"event": "plan_finished", "plan": "smoke", "exit_code": 1, "aggregate_returncode": 1}
    captured_cmd: list[str] = []

    def fake_run(cmd, **_kwargs):  # noqa: ANN001
        captured_cmd.extend(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout=json.dumps(plan_finished) + "\n", stderr="")

    output_file = tmp_path / "github_output.txt"
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))

    code = module.main(["--cycle", "smoke", "--ci-mode", "true", "--persist", "true"])
    assert code == 1
    assert captured_cmd == ["testo", "run", "--cycle", "smoke", "--ci"]

    kv = dict(line.split("=", 1) for line in output_file.read_text(encoding="utf-8").splitlines() if "=" in line)
    assert kv["exit_code"] == "1"
    assert kv["status"] == "failure"
    assert json.loads(kv["summary_json"])["plan"] == "smoke"
    assert Path(kv["summary_path"]) == tmp_path / "testo-summary.json"
    assert Path(kv["summary_path"]).is_file()
