from __future__ import annotations

from pathlib import Path

import pluggy
import pytest

import uqo_core.orchestrator as orch
from uqo_core.command_builders import RunConfig, TestType
from uqo_core.specs import BaseRunnerSpec


pytestmark = [pytest.mark.unit]


def test_load_plugins_registers_python_files(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    plugins_root = tmp_path / "plugins"
    plugins_root.mkdir()
    (plugins_root / "_ignored.py").write_text("x=1\n", encoding="utf-8")
    (plugins_root / "p1.py").write_text("def get_command(config):\n    return None\n", encoding="utf-8")

    monkeypatch.setattr(orch, "_plugins_root", lambda: plugins_root)

    pm = pluggy.PluginManager("uqo")
    pm.add_hookspecs(BaseRunnerSpec)

    orch.load_plugins(pm)
    out = capsys.readouterr().out
    assert "registered p1" in out


def test_create_plugin_manager_without_dropins(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure `load_plugins` not invoked.
    monkeypatch.setattr(orch, "load_plugins", lambda _pm: (_ for _ in ()).throw(AssertionError("should not load")))  # type: ignore[misc]
    pm = orch.create_plugin_manager(load_dropins=False)
    assert isinstance(pm, pluggy.PluginManager)


def test_create_plugin_manager_registers_safe_builtin_hooks(tmp_path: Path) -> None:
    pm = orch.create_plugin_manager(load_dropins=False)
    cfg = RunConfig(
        test_type=TestType.PYTEST,
        target_repo=tmp_path / "repo",
        shared_allure_results_dir=tmp_path / "allure-results",
    )

    assert pm.hook.get_command(config=cfg) is None
    assert pm.hook.setup_env(config=cfg) is None
    assert pm.hook.collect_artifacts(run_id="run-123") == []

