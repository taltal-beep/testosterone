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

import logging
import tomllib
from pathlib import Path
from typing import Any

import yaml

from testo_core import plugins
from testo_core.config.affected import parse_affected
from testo_core.config.errors import ConfigDiscoveryError, ConfigValidationError
from testo_core.config.schema import Defaults, Plan, Stage, TestosteroneConfig
from testo_core.config.sections import (
    parse_cycle,
    parse_defaults,
    parse_quarantine,
    parse_reporters,
    parse_stage,
    parse_version,
    validate_artifact_name,
)
from testo_core.resources.pools import parse_resources

logger = logging.getLogger(__name__)

_DEFAULT_PLAN_NAME = "default"


def _candidate_paths(cwd: Path) -> list[Path]:
    return [
        cwd / "testosterone.yaml",
        cwd / "testosterone.yml",
        cwd / "pyproject.toml",
    ]


def discover_and_load(
    *, config_path: Path | None = None, cwd: Path | None = None
) -> TestosteroneConfig:
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


def load_config_or_defaults(*, config_path: Path | None = None) -> TestosteroneConfig:
    """The given or discovered config; built-in defaults when none is found.

    For ``testo ingest`` and the ingest endpoint, which need no cycles from the
    file, only its reporters and paths when there is one. An explicit
    *config_path* that doesn't exist still raises.
    """
    if config_path is not None:
        return discover_and_load(config_path=config_path)
    try:
        return discover_and_load()
    except ConfigDiscoveryError:
        return TestosteroneConfig(version=1, defaults=Defaults())


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

    if "cycles" in raw or "plans" in raw:
        return _build_cycle_config(raw, config_dir=config_dir, source=source)
    if "runs" in raw:
        return _build_legacy_runs_config(raw, config_dir=config_dir, source=source)
    if "resources" in raw or "affected" in raw:
        # Only pools (for `testo lease`) or test selection (`testo affected`), no cycles yet.
        return TestosteroneConfig(
            version=parse_version(raw.get("version", 1)),
            defaults=parse_defaults(raw.get("defaults", {}), config_dir=config_dir),
            source_path=source,
            resources=parse_resources(raw.get("resources")),
            affected=parse_affected(raw.get("affected"), config_dir=config_dir),
        )
    if {"test_type", "target_repo"}.issubset(raw):
        # Single legacy run, no `runs:` wrapper.
        return _build_legacy_runs_config({"runs": [raw]}, config_dir=config_dir, source=source)

    raise ConfigValidationError(
        f"config at {source} has neither a 'cycles:' nor a 'runs:' section."
    )


def _build_cycle_config(
    raw: dict[str, Any], *, config_dir: Path, source: Path
) -> TestosteroneConfig:
    version = parse_version(raw.get("version", 1))
    defaults = parse_defaults(raw.get("defaults", {}), config_dir=config_dir)
    # Canonical: cycles. Legacy: plans.
    cycles_raw = raw.get("cycles")
    if cycles_raw is None:
        cycles_raw = raw.get("plans")
    if not isinstance(cycles_raw, dict) or not cycles_raw:
        raise ConfigValidationError("'cycles:' must be a non-empty mapping.")
    shared_quarantine = parse_quarantine(raw.get("quarantine"), where="top-level")
    pools = parse_resources(raw.get("resources"))
    cycles: dict[str, Plan] = {}
    for cycle_name, cycle_raw in cycles_raw.items():
        name_key = str(cycle_name)
        if name_key == "all":
            raise ConfigValidationError(
                "cycle name 'all' is reserved for `testo run --cycle all` (run every cycle). "
                "Rename this cycle in your config."
            )
        validate_artifact_name(name_key, kind="cycle name")
        cycle = parse_cycle(
            cycle_name=name_key,
            cycle_raw=cycle_raw or {},
            defaults=defaults,
            config_dir=config_dir,
            shared_quarantine=shared_quarantine,
            pools=pools,
        )
        cycles[cycle.name] = cycle
    reporters = parse_reporters(raw.get("reporters"), config_dir=config_dir)
    return TestosteroneConfig(
        version=version,
        defaults=defaults,
        cycles=cycles,
        reporters=reporters,
        source_path=source,
        resources=pools,
        affected=parse_affected(raw.get("affected"), config_dir=config_dir),
    )


def _build_legacy_runs_config(
    raw: dict[str, Any], *, config_dir: Path, source: Path
) -> TestosteroneConfig:
    """Wrap a legacy flat ``runs: [...]`` config into a single anonymous plan."""
    runs_raw = raw.get("runs")
    if not isinstance(runs_raw, list) or not runs_raw:
        raise ConfigValidationError("'runs:' must be a non-empty list.")
    defaults = parse_defaults(raw.get("defaults", {}), config_dir=config_dir)
    stages: list[Stage] = []
    for idx, run in enumerate(runs_raw, start=1):
        if not isinstance(run, dict):
            raise ConfigValidationError(f"runs[{idx}] must be a mapping.")
        framework = str(run.get("test_type") or run.get("framework") or "").strip()
        if not framework:
            raise ConfigValidationError(f"runs[{idx}] is missing 'test_type' / 'framework'.")
        if framework == "behave_native":
            framework = "behave"
        if framework not in plugins.framework_names():
            raise ConfigValidationError(
                f"runs[{idx}] unsupported framework {framework!r}; "
                f"supported: {sorted(plugins.framework_names())}"
            )
        stage = parse_stage(
            stage_raw={
                "name": run.get("name", f"{framework}-{idx}"),
                "framework": framework,
                "target_repo": run.get("target_repo"),
                "args": run.get("cli_args") or run.get("args"),
                "timeout_s": run.get("timeout_s"),
                "extra_env": run.get("extra_env"),
                "junit_xml": run.get("junit_xml"),
            },
            defaults=defaults,
            config_dir=config_dir,
        )
        stages.append(stage)
    plan = Plan(
        name=_DEFAULT_PLAN_NAME,
        description="Legacy 'runs:' shim.",
        stages=tuple(stages),
        trigger=None,
        quarantine=parse_quarantine(raw.get("quarantine"), where="top-level"),
    )
    reporters = parse_reporters(raw.get("reporters"), config_dir=config_dir)
    return TestosteroneConfig(
        version=parse_version(raw.get("version", 1)),
        defaults=defaults,
        cycles={plan.name: plan},
        reporters=reporters,
        source_path=source,
        resources=parse_resources(raw.get("resources")),
        affected=parse_affected(raw.get("affected"), config_dir=config_dir),
    )
