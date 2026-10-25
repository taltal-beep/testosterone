"""pytest plugin: ``pytest --testo`` records the session as a run, with no CI step or config.

Installed with testo-core (entry point ``pytest11``), and inert until asked:
``--testo`` (or ``--testo-cycle NAME``, or ``TESTO_RECORD=1``) turns it on.
The session's results are written as JUnit XML (pytest's own ``--junitxml``,
or a temporary file when that isn't set) and recorded exactly like
``testo ingest`` would: same run record, same history, same reporters. With
``--testo-server`` (or ``TESTO_SERVER_URL``) they go to a team server instead.

Recording never changes pytest's outcome: a problem is a warning line in the
summary. Under pytest-xdist only the controller records. This module is
imported by every pytest run on a machine with testo-core installed, so it
imports nothing of testo-core until a run is actually recorded.
"""

from __future__ import annotations

import io
import os
import shutil
import tempfile
from pathlib import Path

import pytest

_RECORD_ENV = "TESTO_RECORD"
# Exit codes after which there is nothing worth recording: interrupted,
# internal error, usage error, no tests collected.
_NOTHING_RAN = frozenset({2, 3, 4, 5})
_TEMP_DIR = pytest.StashKey[Path]()
_SUMMARY = pytest.StashKey[str]()


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("testo", "Testosterone: record this session as a run")
    group.addoption(
        "--testo",
        action="store_true",
        default=False,
        help="Record this session in Testosterone's run history (see it with `testo ui`).",
    )
    group.addoption(
        "--testo-cycle",
        default=None,
        metavar="NAME",
        help="Cycle to record under (default: the rootdir's name). Implies --testo.",
    )
    group.addoption(
        "--testo-tier",
        default="unit",
        choices=("unit", "integration", "e2e"),
        help="Test-pyramid tier of these tests (default: unit).",
    )
    group.addoption(
        "--testo-server",
        default=None,
        metavar="URL",
        help="Upload to this Testosterone server instead of recording locally "
        "(default: $TESTO_SERVER_URL). The token comes from $TESTO_API_TOKEN.",
    )


def _enabled(config: pytest.Config) -> bool:
    if hasattr(config, "workerinput"):  # a pytest-xdist worker; the controller records
        return False
    return bool(
        config.getoption("testo")
        or config.getoption("testo_cycle")
        or os.environ.get(_RECORD_ENV, "").strip().lower() in ("1", "true", "yes")
    )


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    # Before pytest's junitxml plugin reads the option, so it writes the report for us.
    if not _enabled(config) or config.option.xmlpath:
        return
    # Inside the rootdir when it can be, so the run records the checkout's git
    # branch and commit; removed again when the session ends.
    try:
        folder = Path(tempfile.mkdtemp(prefix=".testo-", dir=config.rootpath))
    except OSError:
        folder = Path(tempfile.mkdtemp(prefix="testo-pytest-"))
    config.option.xmlpath = str(folder / "session.xml")
    config.stash[_TEMP_DIR] = folder


def _cycle(config: pytest.Config) -> str:
    return (config.getoption("testo_cycle") or config.rootpath.name or "pytest").strip()


def _repo(config: pytest.Config, xml: Path) -> Path:
    """The rootdir when the report is inside it (its git branch and commit are recorded), else the report's folder."""
    root = config.rootpath.resolve()
    return root if root in xml.parents else xml.parent


def _record(config: pytest.Config, xml: Path) -> str:
    """Record *xml*; the line to show in the terminal summary."""
    from rich.console import Console

    from testo_core.cli.runner import execute_ingest_command
    from testo_core.cli.ui.console import _THEME

    cycle = _cycle(config)
    server = config.getoption("testo_server") or os.environ.get("TESTO_SERVER_URL") or None
    # The run's panels would repeat pytest's own summary; keep them for the error case.
    quiet = Console(file=io.StringIO(), width=120, theme=_THEME, no_color=True)
    exit_code = execute_ingest_command(
        console=quiet,
        reports=[str(xml)],
        cycle=cycle,
        stage="pytest",
        tier=config.getoption("testo_tier"),
        repo=_repo(config, xml),
        config_path=None,
        ci=False,
        persist=True,
        server=server,
        token=os.environ.get("TESTO_API_TOKEN") or None,
    )
    # 0 and 1 (tests failed) are both a recorded run; anything else didn't record.
    if exit_code not in (0, 1):
        last = quiet.file.getvalue().strip().splitlines()  # type: ignore[attr-defined]
        detail = f": {last[-1]}" if last else ""
        return f"testo: could not record this session (exit {exit_code}){detail}"
    where = f"on {server}" if server else "here; see it with `testo ui`"
    return f"testo: recorded this session as a run of cycle '{cycle}' ({where})"


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    # trylast: after pytest's junitxml plugin has written the report.
    config = session.config
    if not _enabled(config):
        return
    temp = config.stash.get(_TEMP_DIR, None)
    xml = Path(config.option.xmlpath)
    try:
        if int(exitstatus) in _NOTHING_RAN or not xml.is_file():
            return
        config.stash[_SUMMARY] = _record(config, xml.resolve())
    except Exception as exc:  # noqa: BLE001 — recording must never break the test run
        config.stash[_SUMMARY] = f"testo: could not record this session: {exc}"
    finally:
        if temp is not None:
            shutil.rmtree(temp, ignore_errors=True)


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter, config: pytest.Config
) -> None:
    line = config.stash.get(_SUMMARY, None)
    if line:
        terminalreporter.write_line(line)
