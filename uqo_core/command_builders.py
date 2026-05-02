from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence


class TestType(str, Enum):
    # Prevent pytest from attempting to collect this Enum as a test class.
    __test__ = False
    PYTEST = "pytest"
    BEHAVEX = "behavex"
    BEHAVE_NATIVE = "behave_native"
    LOCUST = "locust"


@dataclass(frozen=True)
class RunConfig:
    test_type: TestType
    target_repo: Path
    shared_allure_results_dir: Path
    artifacts_root: Path | None = None

    # Optional knobs (kept minimal for Phase 2 bootstrap)
    pytest_args: Sequence[str] = ()
    behavex_args: Sequence[str] = ()
    behave_native_args: Sequence[str] = ()
    locust_args: Sequence[str] = ()

    # For locust convenience when running headless from orchestrator
    locustfile: str = "locustfile.py"

    # Locust headless automation
    locust_headless: bool = True
    locust_users: int = 10
    locust_spawn_rate: int = 2
    locust_run_time: str = "1m"
    locust_only_summary: bool = True

    # Extra environment variables to inject into subprocess
    extra_env: Mapping[str, str] | None = None

    # Optional stable run identifier (used for metadata + result isolation)
    run_id: str | None = None

    # Denormalized test type string for UI (defaults to ``test_type.value`` via env if omitted)
    last_test_type: str | None = None

    # BehaveX parallel defaults (orchestrator injects unless CLI overrides)
    behavex_parallel_processes: int = 4
    behavex_parallel_scheme: str = "feature"

    # Execution safety
    # - timeout_s: hard stop to prevent silent hangs (None = no timeout)
    # - heartbeat_s: emit a "still running" line if no output is seen
    timeout_s: float | None = None
    heartbeat_s: float = 10.0


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
    env["UQO_LAST_TEST_TYPE"] = cfg.last_test_type or cfg.test_type.value

    if cfg.test_type == TestType.PYTEST:
        argv = _build_pytest(cfg, shared_dir)
    elif cfg.test_type == TestType.BEHAVEX:
        argv = _build_behavex(cfg, shared_dir)
    elif cfg.test_type == TestType.BEHAVE_NATIVE:
        argv = _build_behave_native(cfg, shared_dir)
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


def _build_behave_native(cfg: RunConfig, shared_dir: Path) -> list[str]:
    """
    Native Behave CLI with Allure formatter.

    Uses ``UQO_SHARED_ALLURE_RESULTS_DIR`` as the Allure output root so the orchestrator can
    enforce per-framework paths (e.g. ``artifacts/allure-results/behave_native``).
    """
    # Per contract: output must be exactly cfg.shared_allure_results_dir
    out_dir = cfg.shared_allure_results_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_dir_str = str(cfg.shared_allure_results_dir.expanduser().resolve())

    # Required flags (explicit, stable shape)
    argv: list[str] = [
        "behave",
        "-f",
        "allure_behave.formatter:AllureFormatter",
        "-o",
        out_dir_str,
    ]
    argv.extend(list(cfg.behave_native_args))

    has_explicit_target = any(
        (a and not str(a).startswith("-")) or str(a).endswith(".feature") or "--paths" in str(a) for a in cfg.behave_native_args
    )
    if not has_explicit_target:
        argv.append(str((cfg.target_repo.expanduser().resolve() / "features").resolve()))
    return argv


def _strip_behavex_output_folder_args(args: Sequence[str]) -> list[str]:
    """Remove `-o` / `--output-folder` so the orchestrator controls BehaveX output location."""
    out: list[str] = []
    i = 0
    a = list(args)
    while i < len(a):
        if a[i] in ("-o", "--output-folder"):
            i += 2
            continue
        out.append(a[i])
        i += 1
    return out


def _argv_contains_parallel_processes(argv: list[str]) -> bool:
    return "--parallel-processes" in argv


def _argv_contains_parallel_scheme(argv: list[str]) -> bool:
    return "--parallel-scheme" in argv


def _argv_has_formatter(argv: list[str]) -> bool:
    return "-f" in argv or "--formatter" in argv or any(a.startswith("--formatter=") for a in argv)


def _build_behavex(cfg: RunConfig, shared_dir: Path) -> list[str]:
    """
    BehaveX runs in parallel and writes native HTML under ``-o`` (see ``report.html``).

    For Allure JSON, use BehaveX's own Allure formatter (not ``allure_behave`` directly) and
    direct its output to the shared Allure results directory (the orchestrator controls the actual path).
    """
    artifacts_root = (cfg.artifacts_root or Path("artifacts")).expanduser().resolve()
    behavex_out = artifacts_root / "behave_reports"
    behavex_out.mkdir(parents=True, exist_ok=True)

    shared_resolved = shared_dir.expanduser().resolve()

    argv: list[str] = ["behavex", "-o", str(behavex_out)]
    argv.extend(_strip_behavex_output_folder_args(cfg.behavex_args))

    if not _argv_contains_parallel_processes(argv):
        argv.extend(["--parallel-processes", str(int(cfg.behavex_parallel_processes))])
    if not _argv_contains_parallel_scheme(argv):
        argv.extend(["--parallel-scheme", str(cfg.behavex_parallel_scheme)])

    # BehaveX requires its own formatter wrapper; using ``allure_behave.formatter:AllureFormatter``
    # directly can fail with missing ``stream_opener`` / ``config`` under some versions.
    if not _argv_has_formatter(argv):
        argv.extend(
            [
                "--formatter=behavex.outputs.formatters.allure_behavex_formatter:AllureBehaveXFormatter",
                "--formatter-outdir",
                str(shared_resolved),
            ]
        )
    return argv


def _build_locust(cfg: RunConfig, shared_dir: Path) -> list[str]:
    # Locust does not emit Allure JSON. We generate Locust's native HTML report instead.
    locustfile_path = (cfg.target_repo / cfg.locustfile).as_posix()

    # Use locust_custom (not "locust") so PYTHONPATH does not shadow site-packages `locust`.
    hook_path = (Path(__file__).resolve().parents[1] / "drop_in_hooks" / "locust_custom" / "locust_hooks.py").resolve().as_posix()

    # Locust supports multiple locustfiles separated by commas in a single -f argument.
    # This avoids needing multiple -f flags (which can be ambiguous across versions).
    combined = f"{locustfile_path},{hook_path}"

    argv: list[str] = ["locust", "-f", combined]
    argv.extend(list(cfg.locust_args))

    # Headless defaults (can still be overridden by explicit locust_args)
    if cfg.locust_headless and "--headless" not in argv:
        argv.append("--headless")
    if cfg.locust_only_summary and "--only-summary" not in argv:
        argv.append("--only-summary")
    if "-u" not in argv and "--users" not in argv:
        argv.extend(["-u", str(int(cfg.locust_users))])
    if "-r" not in argv and "--spawn-rate" not in argv:
        argv.extend(["-r", str(int(cfg.locust_spawn_rate))])
    if "-t" not in argv and "--run-time" not in argv:
        argv.extend(["-t", str(cfg.locust_run_time)])

    # Headless HTML report → <shared_allure_results_dir>/locust_report.html (mirrored to static/ by runners)
    if cfg.locust_headless and "--html" not in argv:
        shared_resolved = shared_dir.expanduser().resolve()
        shared_resolved.mkdir(parents=True, exist_ok=True)
        html_path = (shared_resolved / "locust_report.html").resolve()
        argv.extend(["--html", str(html_path)])

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

