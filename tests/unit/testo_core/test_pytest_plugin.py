"""``pytest --testo`` records the session as a run (testo_core/pytest_plugin.py).

Each test runs pytest in a subprocess on a two-test project, as a user would.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

_TESTS = """
def test_ok():
    assert True


def test_bad():
    assert 1 == 2
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "shop"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_demo.py").write_text(_TESTS, encoding="utf-8")
    # A rootdir marker, so pytest doesn't walk up into this repo's config.
    (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    return root


def _pytest(root: Path, db: Path, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
    environ = {k: v for k, v in os.environ.items() if not k.startswith(("TESTO_", "PYTEST_"))}
    environ.update({"DATABASE_URL": f"sqlite:///{db}", **env})
    for ci_var in ("CI", "GITHUB_ACTIONS", "GITLAB_CI"):
        environ.pop(ci_var, None)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
        cwd=root,
        env=environ,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _runs(db: Path) -> list[tuple[str | None, int, int | None]]:
    code = (
        "from testo_core.history.read_model import list_recent_runs\n"
        "print([(r.cycle, r.returncode, r.failed) for r in list_recent_runs(limit=10)])"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db}"},
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return eval(out.stdout.strip())  # noqa: S307 — our own repr of a list of tuples


def test_records_the_session_and_keeps_pytests_exit_code(project: Path, tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    result = _pytest(project, db, "--testo-cycle", "shop-unit")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "testo: recorded this session as a run of cycle 'shop-unit'" in result.stdout
    assert _runs(db) == [("shop-unit", 1, 1)]
    # The temporary report folder is gone.
    assert not list(project.glob(".testo-*"))


def test_inert_without_the_flag(project: Path, tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    result = _pytest(project, db)
    assert result.returncode == 1
    assert "testo:" not in result.stdout
    assert not db.exists() or _runs(db) == []


def test_a_recording_problem_never_changes_the_outcome(project: Path, tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    # Nothing listens on port 9: the upload fails, the tests' result stands.
    result = _pytest(project, db, "--testo", "--testo-server", "http://127.0.0.1:9", "-k", "ok")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "testo: could not record this session" in result.stdout


def _verbose_lines(stdout: str) -> list[str]:
    """``tests/x.py::test_y PASSED`` lines, in the order the tests ran."""
    return [line for line in stdout.splitlines() if re.search(r"::test_\w+ (PASSED|FAILED)", line)]


def test_failed_first_runs_last_runs_failures_first(project: Path, tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    recorded = _pytest(project, db, "--testo-cycle", "shop")
    assert recorded.returncode == 1, recorded.stdout + recorded.stderr

    result = _pytest(project, db, "-vv", "--testo-failed-first", "--testo-cycle", "shop")
    assert result.returncode == 1, result.stdout + result.stderr
    lines = _verbose_lines(result.stdout)
    assert "test_bad" in lines[0] and "test_ok" in lines[1], result.stdout
    assert "testo: failed first: 1 failed last time" in result.stdout


def test_failed_first_without_history_keeps_pytests_order(project: Path, tmp_path: Path) -> None:
    result = _pytest(project, tmp_path / "empty.db", "-vv", "--testo-failed-first")
    assert result.returncode == 1, result.stdout + result.stderr
    lines = _verbose_lines(result.stdout)
    assert "test_ok" in lines[0], result.stdout
    assert "has no recorded runs yet; kept pytest's order" in result.stdout
