from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence


class TestType(str, Enum):
    PYTEST = "pytest"
    BEHAVEX = "behavex"
    LOCUST = "locust"


@dataclass(frozen=True)
class RunConfig:
    test_type: TestType
    target_repo: Path
    shared_allure_results_dir: Path

    # Optional knobs (kept minimal for Phase 2 bootstrap)
    pytest_args: Sequence[str] = ()
    behavex_args: Sequence[str] = ()
    locust_args: Sequence[str] = ()

    # For locust convenience when running headless from orchestrator
    locustfile: str = "locustfile.py"

    # Extra environment variables to inject into subprocess
    extra_env: Mapping[str, str] | None = None

    # Optional stable run identifier (used for metadata + result isolation)
    run_id: str | None = None


@dataclass(frozen=True)
class BuiltCommand:
    argv: list[str]
    cwd: Path
    env: dict[str, str]


def _base_env(*, shared_allure_results_dir: Path, extra_env: Mapping[str, str] | None) -> dict[str, str]:
    env: dict[str, str] = {}
    env["UQO_SHARED_ALLURE_RESULTS_DIR"] = str(shared_allure_results_dir.resolve())
    if extra_env:
        env.update({str(k): str(v) for k, v in extra_env.items()})
    return env


def build_command(cfg: RunConfig, *, parent_env: Mapping[str, str]) -> BuiltCommand:
    target_repo = cfg.target_repo.expanduser().resolve()
    shared_dir = cfg.shared_allure_results_dir.expanduser().resolve()

    env = dict(parent_env)
    env.update(_base_env(shared_allure_results_dir=shared_dir, extra_env=cfg.extra_env))
    if cfg.run_id:
        env["UQO_RUN_ID"] = str(cfg.run_id)

    if cfg.test_type == TestType.PYTEST:
        argv = _build_pytest(cfg, shared_dir)
    elif cfg.test_type == TestType.BEHAVEX:
        argv = _build_behavex(cfg, shared_dir)
    elif cfg.test_type == TestType.LOCUST:
        argv = _build_locust(cfg, shared_dir)
    else:
        raise ValueError(f"Unsupported test_type: {cfg.test_type}")

    return BuiltCommand(argv=argv, cwd=target_repo, env=env)


def _build_pytest(cfg: RunConfig, shared_dir: Path) -> list[str]:
    argv: list[str] = ["pytest"]
    argv.extend(list(cfg.pytest_args))
    argv.extend(["--alluredir", str(shared_dir.resolve())])
    return argv


def _build_behavex(cfg: RunConfig, shared_dir: Path) -> list[str]:
    # BehaveX is typically invoked as `behavex ...`. Allure integration can be via
    # formatter/config; we keep this as a hook-ready placeholder in Phase 2.
    # The orchestrator still sets UQO_SHARED_ALLURE_RESULTS_DIR for drop-in hooks.
    argv: list[str] = ["behavex"]
    argv.extend(list(cfg.behavex_args))
    # If internal repos use AllureBehave formatter, it often needs a directory;
    # keep this optional and non-breaking.
    # Users can pass explicit args in the UI (Phase 2 expansion).
    if "--allure-dir" not in argv and "--alluredir" not in argv:
        argv.extend(["--allure-dir", str(shared_dir.resolve())])
    return argv


def _build_locust(cfg: RunConfig, shared_dir: Path) -> list[str]:
    # Locust doesn't natively emit Allure results; we rely on drop-in hook module.
    # Runner sets UQO_SHARED_ALLURE_RESULTS_DIR and can inject PYTHONPATH later.
    locustfile_path = (cfg.target_repo / cfg.locustfile).as_posix()

    hook_path = (Path(__file__).resolve().parents[1] / "drop_in_hooks" / "locust" / "locust_hooks.py").resolve().as_posix()

    # Locust supports multiple locustfiles separated by commas in a single -f argument.
    # This avoids needing multiple -f flags (which can be ambiguous across versions).
    combined = f"{locustfile_path},{hook_path}"

    argv: list[str] = ["locust", "-f", combined]
    argv.extend(list(cfg.locust_args))
    # Encourage headless mode default if not provided; user can override.
    if "-H" not in argv and "--host" not in argv:
        # No default host—leave it to locustfile or user.
        pass
    return argv


def coerce_path(p: str) -> Path:
    return Path(p).expanduser()


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def stringify_argv(argv: Sequence[str]) -> str:
    # For display only; avoid shell quoting complexities by showing argv as-is.
    return " ".join(argv)

