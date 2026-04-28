"""Plugin manager + plugin loader for UQO runner orchestration.

This module owns a global ``pluggy.PluginManager`` instance and provides helpers
to load built-in hooks and dynamically discovered plugins from ``plugins/``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pluggy
import docker

from engine.specs import BaseRunnerSpec

# Docker client for the local Docker Desktop socket (macOS dev).
# Keep import-time failures from breaking the UI (e.g., Docker Desktop not running).
try:
    client = docker.from_env()
except Exception:  # pragma: no cover
    client = None


def _plugins_root() -> Path:
    # Repo root is the parent of `engine/`.
    return Path(__file__).resolve().parents[1] / "plugins"


def _load_module_from_path(*, module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load plugin module from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_plugins(pm: pluggy.PluginManager) -> None:
    """Scan ``plugins/`` for ``*.py`` and register each as a plugin."""
    plugins_dir = _plugins_root()
    if not plugins_dir.exists():
        return
    for path in sorted(plugins_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module_name = f"uqo_plugin_{path.stem}"
        mod = _load_module_from_path(module_name=module_name, path=path)
        pm.register(mod, name=path.stem)
        print(f"[plugins] registered {path.stem} ({path.name})")


def create_plugin_manager(*, load_dropins: bool = True) -> pluggy.PluginManager:
    pm = pluggy.PluginManager("uqo")
    pm.add_hookspecs(BaseRunnerSpec)

    # Built-in implementations keep the engine functional with zero user plugins.
    from engine import plugins_builtin

    pm.register(plugins_builtin, name="uqo_builtin")

    if load_dropins:
        load_plugins(pm)

    return pm

