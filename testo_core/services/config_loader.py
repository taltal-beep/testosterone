from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

import yaml

from testo_core.command_builders import TestType
from testo_core.runners import validate_target_repo
from testo_core.services.headless_engine import ConfigValidationError, EngineRunSpec


def _as_tuple_args(value: Any, *, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(a for a in shlex.split(value) if a.strip())
    if isinstance(value, list) and all(isinstance(i, str) for i in value):
        return tuple(value)
    raise ConfigValidationError(f"`{field_name}` must be a string or string list.")


def _as_test_type(value: Any) -> TestType:
    try:
        return TestType(str(value))
    except Exception as exc:
        allowed = ", ".join([t.value for t in TestType])
        raise ConfigValidationError(f"Invalid `test_type`: {value}. Allowed values: {allowed}.") from exc


def _parse_run_item(item: dict[str, Any], *, config_dir: Path) -> EngineRunSpec:
    if not isinstance(item, dict):
        raise ConfigValidationError("Each run entry must be an object.")
    raw_test_type = item.get("test_type")
    if raw_test_type is None:
        raise ConfigValidationError("Missing required `test_type`.")
    raw_target = item.get("target_repo")
    if raw_target is None:
        raise ConfigValidationError("Missing required `target_repo`.")

    test_type = _as_test_type(raw_test_type)
    target_repo = Path(str(raw_target))
    if not target_repo.is_absolute():
        target_repo = (config_dir / target_repo).resolve()
    ok, msg = validate_target_repo(target_repo)
    if not ok:
        raise ConfigValidationError(f"Invalid `target_repo` ({target_repo}): {msg}")

    cli_args = _as_tuple_args(item.get("cli_args"), field_name="cli_args")
    shared_dir_raw = item.get("shared_allure_results_dir")
    shared_dir = None
    if shared_dir_raw is not None:
        shared_dir = Path(str(shared_dir_raw))
        if not shared_dir.is_absolute():
            shared_dir = (config_dir / shared_dir).resolve()

    artifacts_root_raw = item.get("artifacts_root")
    artifacts_root = None
    if artifacts_root_raw is not None:
        artifacts_root = Path(str(artifacts_root_raw))
        if not artifacts_root.is_absolute():
            artifacts_root = (config_dir / artifacts_root).resolve()

    extra_env_value = item.get("extra_env")
    extra_env: dict[str, str] | None = None
    if extra_env_value is not None:
        if not isinstance(extra_env_value, dict):
            raise ConfigValidationError("`extra_env` must be a key/value object.")
        extra_env = {str(k): str(v) for k, v in extra_env_value.items()}

    timeout_s = item.get("timeout_s")
    if timeout_s is not None:
        try:
            timeout_s = float(timeout_s)
        except (TypeError, ValueError) as exc:
            raise ConfigValidationError("`timeout_s` must be numeric.") from exc

    return EngineRunSpec(
        test_type=test_type,
        target_repo=target_repo,
        cli_args=cli_args,
        shared_allure_results_dir=shared_dir,
        artifacts_root=artifacts_root,
        timeout_s=timeout_s,
        extra_env=extra_env,
    )


def load_run_specs_from_yaml(config_path: Path) -> tuple[EngineRunSpec, ...]:
    path = Path(config_path).expanduser().resolve()
    if not path.is_file():
        raise ConfigValidationError(f"Config file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigValidationError(f"Invalid YAML: {exc}") from exc

    if raw is None:
        raise ConfigValidationError("Config file is empty.")

    config_dir = path.parent
    if isinstance(raw, dict) and "runs" in raw:
        runs_raw = raw.get("runs")
        if not isinstance(runs_raw, list) or not runs_raw:
            raise ConfigValidationError("`runs` must be a non-empty list.")
        return tuple(_parse_run_item(item, config_dir=config_dir) for item in runs_raw)

    if isinstance(raw, list):
        if not raw:
            raise ConfigValidationError("Top-level list must not be empty.")
        return tuple(_parse_run_item(item, config_dir=config_dir) for item in raw)

    if isinstance(raw, dict):
        return (_parse_run_item(raw, config_dir=config_dir),)

    raise ConfigValidationError("Unsupported config format. Use an object, list, or {runs: [...]} format.")
