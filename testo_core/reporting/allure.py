"""Thin wrapper around ``allure generate``.

The Allure CLI is optional — if it is missing we surface a structured error
rather than crashing.  This is the only place that should ``shutil.which``
for ``allure``.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


class AllureCLINotFoundError(RuntimeError):
    """Raised when the ``allure`` CLI is not on ``PATH``."""


@dataclass(frozen=True)
class AllureGenerateResult:
    ok: bool
    out_dir: Path
    message: str


def is_allure_available() -> bool:
    return shutil.which("allure") is not None


def generate_html(
    *,
    result_dirs: Sequence[Path],
    out_dir: Path,
    clean: bool = True,
) -> AllureGenerateResult:
    """Invoke ``allure generate`` and capture its result."""
    if not result_dirs:
        return AllureGenerateResult(
            ok=False,
            out_dir=out_dir,
            message="no allure-results directories found.",
        )
    if not is_allure_available():
        raise AllureCLINotFoundError(
            "the 'allure' CLI was not found on PATH. Install it from "
            "https://allurereport.org/docs/install/ or use --format json/junit instead."
        )

    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    argv: list[str] = ["allure", "generate"]
    if clean:
        argv.append("--clean")
    argv.extend(["-o", str(out_dir)])
    argv.extend(str(p.expanduser().resolve()) for p in result_dirs)

    completed = subprocess.run(  # noqa: S603 — argv is built by trusted code
        argv,
        check=False,
        text=True,
        capture_output=True,
    )
    ok = completed.returncode == 0 and (out_dir / "index.html").is_file()
    msg = completed.stdout.strip() or completed.stderr.strip() or (
        "report generated" if ok else f"allure exited {completed.returncode}"
    )
    return AllureGenerateResult(ok=ok, out_dir=out_dir, message=msg)
