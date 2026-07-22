from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from importlib.metadata import version as pkg_version
from pathlib import Path

import pytest

import testo_core

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def _strip_ansi(text: str) -> str:
    """Drop ANSI escape sequences so substring assertions survive Rich/Typer
    colorizing the output (e.g. ``\\x1b[1m--\\x1b[0mci``)."""
    return _ANSI_RE.sub("", text)


def _help_env() -> dict[str, str]:
    """Subprocess env that forces plain, wide help output.

    * ``NO_COLOR=1`` — universal "no ANSI" opt-in (Rich, Click, Typer all honor it).
    * ``TERM=dumb`` — keeps Rich/Click from auto-detecting a TTY.
    * ``COLUMNS=200`` — keeps long flag/usage lines from being wrapped on narrow
      CI runners where ``--help`` panels are otherwise re-flowed.
    """
    return {**os.environ, "NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"}


@pytest.mark.contract
def test_public_version_matches_distribution_metadata() -> None:
    assert testo_core.__version__ == pkg_version("testo-core")


@pytest.mark.contract
def test_console_script_uqo_is_available() -> None:
    which_path = shutil.which("uqo")
    if which_path:
        assert Path(which_path).is_file()
        return
    venv_script = Path(sys.prefix).resolve() / "bin" / "uqo"
    assert venv_script.is_file()


@pytest.mark.contract
def test_console_script_help_works() -> None:
    uqo_path = shutil.which("uqo")
    if uqo_path is None:
        uqo_path = str(Path(sys.prefix).resolve() / "bin" / "uqo")
    proc = subprocess.run(  # noqa: S603
        [uqo_path, "run", "--help"],
        check=False,
        capture_output=True,
        text=True,
        env=_help_env(),
    )
    assert proc.returncode == 0
    stdout = _strip_ansi(proc.stdout)
    stderr = _strip_ansi(proc.stderr)
    # Typer renders the help with capitalised ``Usage:``; remain format-agnostic.
    assert "Usage:" in stdout
    assert "run " in stdout
    # The new Typer CLI replaces ``--stream-json`` with ``--ci`` (NDJSON events).
    assert "--ci" in stdout
    # Deprecation banner must be emitted on stderr from the legacy ``uqo`` shim.
    assert "deprecated" in stderr.lower()


@pytest.mark.contract
def test_new_console_script_testo_works() -> None:
    testo_path = shutil.which("testo")
    if testo_path is None:
        testo_path = str(Path(sys.prefix).resolve() / "bin" / "testo")
    proc = subprocess.run(  # noqa: S603
        [testo_path, "run", "--help"],
        check=False,
        capture_output=True,
        text=True,
        env=_help_env(),
    )
    assert proc.returncode == 0
    stdout = _strip_ansi(proc.stdout)
    assert "Usage:" in stdout
    assert "--ci" in stdout
    assert "--cycle" in stdout


@pytest.mark.contract
def test_python_build_module_available() -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "build", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
