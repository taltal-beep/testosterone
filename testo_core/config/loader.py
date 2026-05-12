"""Discover and parse ``testosterone.yaml`` (or ``[tool.testosterone]``).

Discovery order (first hit wins):

1. ``--config PATH`` argument.
2. ``./testosterone.yaml`` in the current directory.
3. ``./testosterone.yml``.
4. ``[tool.testosterone]`` table inside ``./pyproject.toml``.

The loader **does not** import the engine, runners, or framework adapters —
keep it cheap so ``testo plans list`` is responsive even in cold venvs.

Backwards compatibility: a legacy flat ``runs: [...]`` schema (the one
consumed by the deprecated argparse CLI) is accepted and wrapped into a
single anonymous plan called ``default``.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Mapping

import yaml

from testo_core.config.errors import ConfigDiscoveryError, ConfigValidationError
from testo_core.config.schema import (
    SUPPORTED_FRAMEWORKS,
    Defaults,
    Plan,
    Stage,
    TestosteroneConfig,
)


_DEFAULT_PLAN_NAME = "default"


def _candidate_paths(cwd: Path) -> list[Path]:
    return [
        cwd / "testosterone.yaml",
        cwd / "testosterone.yml",
        cwd / "pyproject.toml",
    ]


def discover_and_load(*, config_path: Path | None = None, cwd: Path | None = None) -> TestosteroneConfig:
    """Discover the config file then call :func:`load_config`.

    If ``config_path`` is provided it is used directly; otherwise the
    discovery order above applies.  ``cwd`` defaults to ``Path.cwd()`` and
    is the only seam tests need to monkeypatch.
    """
    cwd = (cwd or Path.cwd()).expanduser().resolve()
    if config_path is not None:
        path = config_path.expanduser().resolve()
        if not path.is_file():
            raise ConfigDiscoveryError(f"config file not found: {path}")
        return load_config(path)

    for candidate in _candidate_paths(cwd):
        if candidate.is_file():
            return load_config(candidate)
    raise ConfigDiscoveryError(
        f"no testosterone.yaml / testosterone.yml / pyproject.toml [tool.testosterone] found under {cwd}"
    )


def load_config(path: Path) -> TestosteroneConfig:
    """Load and validate one config file."""
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ConfigDiscoveryError(f"config file not found: {path}")

    if path.name == "pyproject.toml":
        raw = _read_pyproject_section(path)
        if raw is None:
            raise ConfigDiscoveryError(
                f"pyproject.toml at {path} has no [tool.testosterone] table."
            )
    else:
        raw = _read_yaml(path)

    return _build_config(raw, source=path)


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - defensive
        raise ConfigValidationError(f"cannot read {path}: {exc}") from exc
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigValidationError(f"invalid YAML in {path}: {exc}") from exc
    if parsed is None:
        raise ConfigValidationError(f"config file {path} is empty.")
    if not isinstance(parsed, (dict, list)):
        raise ConfigValidationError(f"top-level of {path} must be a mapping or list.")
    return parsed if isinstance(parsed, dict) else {"runs": parsed}


def _read_pyproject_section(path: Path) -> dict[str, Any] | None:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigValidationError(f"invalid pyproject.toml at {path}: {exc}") from exc
    return data.get("tool", {}).get("testosterone")


def _build_config(raw: dict[str, Any], *, source: Path) -> TestosteroneConfig:
    config_dir = source.parent

    if "plans" in raw:
        return _build_plan_config(raw, config_dir=config_dir, source=source)
    if "runs" in raw:
        return _build_legacy_runs_config(raw, config_dir=config_dir, source=source)
    if {"test_type", "target_repo"}.issubset(raw):
        # Single legacy run, no `runs:` wrapper.
        return _build_legacy_runs_config({"runs": [raw]}, config_dir=config_dir, source=source)

    raise ConfigValidationError(
        f"config at {source} has neither a 'plans:' nor a 'runs:' section."
    )


def _build_plan_config(raw: dict[str, Any], *, config_dir: Path, source: Path) -> TestosteroneConfig:
    version = int(raw.get("version", 1))
    defaults = _parse_defaults(raw.get("defaults", {}), config_dir=config_dir)
    plans_raw = raw.get("plans")
    if not isinstance(plans_raw, dict) or not plans_raw:
        raise ConfigValidationError("'plans:' must be a non-empty mapping.")
    plans: dict[str, Plan] = {}
    for plan_name, plan_raw in plans_raw.items():
        plan = _parse_plan(
            plan_name=str(plan_name),
            plan_raw=plan_raw or {},
            defaults=defaults,
            config_dir=config_dir,
        )
        plans[plan.name] = plan
    return TestosteroneConfig(version=version, defaults=defaults, plans=plans, source_path=source)


def _build_legacy_runs_config(
    raw: dict[str, Any], *, config_dir: Path, source: Path
) -> TestosteroneConfig:
    """Wrap a legacy flat ``runs: [...]`` config into a single anonymous plan."""
    runs_raw = raw.get("runs")
    if not isinstance(runs_raw, list) or not runs_raw:
        raise ConfigValidationError("'runs:' must be a non-empty list.")
    defaults = _parse_defaults(raw.get("defaults", {}), config_dir=config_dir)
    stages: list[Stage] = []
    for idx, run in enumerate(runs_raw, start=1):
        if not isinstance(run, dict):
            raise ConfigValidationError(f"runs[{idx}] must be a mapping.")
        framework = str(run.get("test_type") or run.get("framework") or "").strip()
        if not framework:
            raise ConfigValidationError(f"runs[{idx}] is missing 'test_type' / 'framework'.")
        if framework == "behave_native":
            framework = "behave"
        if framework not in SUPPORTED_FRAMEWORKS:
            raise ConfigValidationError(
                f"runs[{idx}] unsupported framework {framework!r}; "
                f"supported: {sorted(SUPPORTED_FRAMEWORKS)}"
            )
        stage = _parse_stage(
            stage_raw={
                "name": run.get("name", f"{framework}-{idx}"),
                "framework": framework,
                "target_repo": run.get("target_repo"),
                "args": run.get("cli_args") or run.get("args"),
                "timeout_s": run.get("timeout_s"),
                "extra_env": run.get("extra_env"),
            },
            defaults=defaults,
            config_dir=config_dir,
        )
        stages.append(stage)
    plan = Plan(name=_DEFAULT_PLAN_NAME, description="Legacy 'runs:' shim.", stages=tuple(stages))
    return TestosteroneConfig(
        version=int(raw.get("version", 1)),
        defaults=defaults,
        plans={plan.name: plan},
        source_path=source,
    )


def _parse_defaults(raw: Any, *, config_dir: Path) -> Defaults:
    if not isinstance(raw, dict):
        raise ConfigValidationError("'defaults:' must be a mapping.")
    target_repo = _resolve_path(raw.get("target_repo", "."), config_dir=config_dir)
    artifacts_root = _resolve_path(raw.get("artifacts_root", "artifacts"), config_dir=config_dir)
    timeout_s = raw.get("timeout_s", 600.0)
    workers = int(raw.get("workers", 4))
    extra_env = _normalise_env(raw.get("extra_env"))
    return Defaults(
        target_repo=target_repo,
        artifacts_root=artifacts_root,
        timeout_s=float(timeout_s) if timeout_s is not None else None,
        workers=workers,
        extra_env=extra_env,
    )


def _parse_plan(*, plan_name: str, plan_raw: dict[str, Any], defaults: Defaults, config_dir: Path) -> Plan:
    if not isinstance(plan_raw, dict):
        raise ConfigValidationError(f"plan {plan_name!r} must be a mapping.")
    description = plan_raw.get("description")
    stages_raw = plan_raw.get("stages")
    if not isinstance(stages_raw, list) or not stages_raw:
        raise ConfigValidationError(f"plan {plan_name!r} must define a non-empty 'stages:' list.")
    stages = tuple(
        _parse_stage(stage_raw=item, defaults=defaults, config_dir=config_dir)
        for item in stages_raw
    )
    return Plan(name=plan_name, description=description, stages=stages)


def _parse_stage(*, stage_raw: Mapping[str, Any], defaults: Defaults, config_dir: Path) -> Stage:
    if not isinstance(stage_raw, Mapping):
        raise ConfigValidationError("stage entries must be mappings.")
    name = str(stage_raw.get("name") or "").strip()
    framework = str(stage_raw.get("framework") or "").strip()
    if not name:
        raise ConfigValidationError("stage is missing 'name'.")
    if not framework:
        raise ConfigValidationError(f"stage {name!r} is missing 'framework'.")
    if framework == "behave_native":
        framework = "behave"
    if framework not in SUPPORTED_FRAMEWORKS:
        raise ConfigValidationError(
            f"stage {name!r} has unsupported framework {framework!r}; "
            f"supported: {sorted(SUPPORTED_FRAMEWORKS)}"
        )

    target_repo_raw = stage_raw.get("target_repo")
    target_repo = (
        _resolve_path(target_repo_raw, config_dir=config_dir)
        if target_repo_raw is not None
        else defaults.target_repo
    )

    args_raw = stage_raw.get("args")
    if args_raw is None:
        args: tuple[str, ...] = ()
    elif isinstance(args_raw, str):
        import shlex

        args = tuple(shlex.split(args_raw))
    elif isinstance(args_raw, list):
        if not all(isinstance(a, (str, int, float)) for a in args_raw):
            raise ConfigValidationError(f"stage {name!r}: 'args' must be a list of scalars.")
        args = tuple(str(a) for a in args_raw)
    else:
        raise ConfigValidationError(f"stage {name!r}: 'args' must be a string or list.")

    workers = int(stage_raw.get("workers", defaults.workers))
    timeout_raw = stage_raw.get("timeout_s", defaults.timeout_s)
    timeout_s = float(timeout_raw) if timeout_raw is not None else None
    if_expr = stage_raw.get("if")
    if if_expr is not None and not isinstance(if_expr, str):
        raise ConfigValidationError(f"stage {name!r}: 'if' must be a string.")

    extra_env = _normalise_env(stage_raw.get("extra_env")) or defaults.extra_env
    return Stage(
        name=name,
        framework=framework,
        target_repo=target_repo,
        args=args,
        workers=workers,
        timeout_s=timeout_s,
        if_expr=if_expr,
        extra_env=extra_env,
    )


def _resolve_path(value: Any, *, config_dir: Path) -> Path:
    if value is None:
        return config_dir
    p = Path(str(value)).expanduser()
    return p if p.is_absolute() else (config_dir / p).resolve()


def _normalise_env(value: Any) -> tuple[tuple[str, str], ...]:
    if value is None:
        return ()
    if not isinstance(value, Mapping):
        raise ConfigValidationError("'extra_env' must be a mapping of strings.")
    out: list[tuple[str, str]] = []
    for k, v in value.items():
        out.append((str(k), str(v)))
    return tuple(out)
