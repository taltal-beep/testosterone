from __future__ import annotations

from pathlib import Path

import pytest

from testo_core.command_builders import TestType
from testo_core.services import ConfigValidationError, load_run_specs_from_yaml


def test_load_single_run_yaml(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    cfg = tmp_path / "run.yaml"
    cfg.write_text(
        "\n".join(
            [
                "test_type: pytest",
                f"target_repo: {target}",
                "cli_args: -m smoke -q",
                "timeout_s: 120",
            ]
        ),
        encoding="utf-8",
    )

    specs = load_run_specs_from_yaml(cfg)
    assert len(specs) == 1
    assert specs[0].test_type == TestType.PYTEST
    assert specs[0].target_repo == target
    assert specs[0].cli_args == ("-m", "smoke", "-q")
    assert specs[0].timeout_s == 120.0


def test_load_multi_run_yaml(tmp_path: Path) -> None:
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    cfg = tmp_path / "runs.yaml"
    cfg.write_text(
        "\n".join(
            [
                "runs:",
                "  - test_type: pytest",
                f"    target_repo: {repo_a}",
                "    cli_args: ['-q']",
                "  - test_type: behavex",
                f"    target_repo: {repo_b}",
                "    timeout_s: 300",
            ]
        ),
        encoding="utf-8",
    )

    specs = load_run_specs_from_yaml(cfg)
    assert [s.test_type for s in specs] == [TestType.PYTEST, TestType.BEHAVEX]
    assert specs[1].timeout_s == 300.0


def test_load_yaml_rejects_invalid_test_type(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    cfg = tmp_path / "bad.yaml"
    cfg.write_text(
        "\n".join(
            [
                "test_type: invalid",
                f"target_repo: {target}",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError, match="Invalid `test_type`"):
        load_run_specs_from_yaml(cfg)
