"""Pytest adapter — emits ``--alluredir`` pointing at the per-stage tree."""

from __future__ import annotations

from pathlib import Path

from testo_core.frameworks.base import NativeReport


def _args_set_explicit_pytest_config(args: list[str]) -> bool:
    """True when the user already chose a pytest config file (do not inject ``-c``)."""
    i = 0
    while i < len(args):
        a = str(args[i])
        if a in ("-c", "--config", "--config-file"):
            return True
        if a.startswith(("--config-file=", "--config=")):
            return True
        i += 1
    return False


class PytestAdapter:
    name: str = "pytest"

    def results_subdir(self) -> str:
        return "pytest"

    def build_argv(
        self,
        *,
        target_repo: Path,
        results_dir: Path,
        stage_args: tuple[str, ...],
        workers: int,
    ) -> list[str]:
        del workers
        repo = target_repo.expanduser().resolve()
        argv: list[str] = ["pytest"]
        args = list(stage_args)
        if not _args_set_explicit_pytest_config(args):
            ini = repo / "pytest.ini"
            if ini.is_file():
                argv.extend(["-c", str(ini.resolve())])
        argv.extend(args)
        # One token, not two: pytest picks its rootdir (and so the target's own
        # config, e.g. ``pythonpath``) from the common ancestor of every
        # non-option argument that exists on disk, and a separate path token
        # after ``--alluredir`` counts as one. With results under testosterone's
        # ``artifacts/``, a target inside the checkout would get testosterone's
        # rootdir and ``pytest.ini`` instead of its own.
        argv.append(f"--alluredir={results_dir.resolve()}")
        return argv

    def native_report(self, stage_dir: Path) -> NativeReport | None:
        del stage_dir  # pytest has no native HTML report of its own
        return None
