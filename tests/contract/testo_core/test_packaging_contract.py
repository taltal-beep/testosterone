from __future__ import annotations

import shutil
import subprocess
import sys
from importlib.metadata import version as pkg_version
from pathlib import Path

import pytest

import testo_core


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
    )
    assert proc.returncode == 0
    # Typer renders the help with capitalised ``Usage:``; remain format-agnostic.
    assert "Usage:" in proc.stdout
    assert "run " in proc.stdout
    # The new Typer CLI replaces ``--stream-json`` with ``--ci`` (NDJSON events).
    assert "--ci" in proc.stdout
    # Deprecation banner must be emitted on stderr from the legacy ``uqo`` shim.
    assert "deprecated" in proc.stderr.lower()


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
    )
    assert proc.returncode == 0
    assert "Usage:" in proc.stdout
    assert "--plan" in proc.stdout
    assert "--ci" in proc.stdout


@pytest.mark.contract
def test_python_build_module_available() -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "build", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
