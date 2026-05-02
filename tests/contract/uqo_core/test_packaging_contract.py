from __future__ import annotations

import shutil
import subprocess
import sys
from importlib.metadata import version as pkg_version
from pathlib import Path

import pytest

import uqo_core


@pytest.mark.contract
def test_public_version_matches_distribution_metadata() -> None:
    assert uqo_core.__version__ == pkg_version("uqo-core")


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
    assert "usage: uqo run" in proc.stdout
    assert "--stream-json" in proc.stdout


@pytest.mark.contract
def test_python_build_module_available() -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "build", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
