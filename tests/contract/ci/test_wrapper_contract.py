from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

from testo_core.cli import SUMMARY_SCHEMA_KEYS


def _load_wrapper_module():
    script = Path("integrations/github-action/run_uqo_action.py").resolve()
    spec = importlib.util.spec_from_file_location("run_uqo_action_contract", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_action_contract_has_required_inputs_outputs() -> None:
    payload = yaml.safe_load(Path("integrations/github-action/action.yml").read_text(encoding="utf-8"))
    assert set(payload["inputs"].keys()) == {
        "config-path",
        "ci-mode",
        "ghost-mode",
        "stream-json",
        "persist",
        "runner-image",
        "runner-prebuilt",
        "python-version",
    }
    assert set(payload["outputs"].keys()) == {"exit_code", "run_id", "summary_json", "summary_path", "status"}


def test_wrapper_uses_uqo_run_ci_command_shape() -> None:
    module = _load_wrapper_module()
    cmd = module.build_command(config_path="config.yml", ci_mode=True, stream_json=False, persist=True, ghost_mode="auto")
    assert cmd[:4] == ["uqo", "run", "--config", "config.yml"]
    assert "--ci" in cmd


def test_github_fixture_is_one_line_consumer() -> None:
    workflow = Path("tests/fixtures/ci/github_workflow_minimal.yml").read_text(encoding="utf-8")
    assert "uses: ariel-evn/uqo-action@v1" in workflow


def test_gitlab_template_exposes_runner_image_controls() -> None:
    template = Path("ci/gitlab/uqo.gitlab-ci.yml").read_text(encoding="utf-8")
    assert "UQO_RUNNER_IMAGE" in template
    assert "UQO_RUNNER_PREBUILT" in template


def test_core_summary_schema_keys_unchanged() -> None:
    assert SUMMARY_SCHEMA_KEYS == (
        "schema_version",
        "trigger_source",
        "ci_mode",
        "persist",
        "exit_code",
        "aggregate_returncode",
        "started_at",
        "finished_at",
        "duration_s",
        "runs",
        "error",
    )
