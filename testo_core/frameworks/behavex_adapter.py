"""BehaveX adapter — parallel Behave plus its Allure formatter wrapper."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path


class BehaveXAdapter:
    name: str = "behavex"

    def results_subdir(self) -> str:
        return "behavex"

    def build_argv(
        self,
        *,
        target_repo: Path,
        results_dir: Path,
        stage_args: tuple[str, ...],
        workers: int,
    ) -> list[str]:
        del target_repo  # behavex picks up its own working dir
        behavex_output = results_dir.parent / "behave_reports"
        behavex_output.mkdir(parents=True, exist_ok=True)
        results_dir.mkdir(parents=True, exist_ok=True)

        argv: list[str] = ["behavex", "-o", str(behavex_output.resolve())]
        argv.extend(_strip_output_folder_flags(stage_args))

        if not _contains(argv, "--parallel-processes"):
            argv.extend(["--parallel-processes", str(max(1, int(workers)))])
        if not _contains(argv, "--parallel-scheme"):
            argv.extend(["--parallel-scheme", "feature"])

        if not _has_formatter(argv):
            argv.extend(
                [
                    "--formatter=behavex.outputs.formatters.allure_behavex_formatter:AllureBehaveXFormatter",
                    "--formatter-outdir",
                    str(results_dir.resolve()),
                ]
            )
        return argv


def _strip_output_folder_flags(args: Sequence[str]) -> list[str]:
    out: list[str] = []
    i = 0
    items = list(args)
    while i < len(items):
        if items[i] in ("-o", "--output-folder"):
            i += 2
            continue
        out.append(items[i])
        i += 1
    return out


def _contains(argv: list[str], flag: str) -> bool:
    return any(arg == flag or arg.startswith(f"{flag}=") for arg in argv)


def _has_formatter(argv: list[str]) -> bool:
    return any(
        arg in ("-f", "--formatter") or arg.startswith("--formatter=") for arg in argv
    )
