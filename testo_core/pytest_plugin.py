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

It also hands out keys from a resource pool (``testo_core/resources/``): with
``--testo-resource POOL``, or inside a stage with ``resources:`` (which sets
``TESTO_RESOURCE_SPEC``), each test process (each pytest-xdist worker, never
the controller) holds its own key for the session, or each test gets one
(``per: test``). The key is in ``TESTO_RESOURCE_ID`` and the ``testo_resource``
fixture.

And it splits a suite into shards of about equal time: ``--testo-shard I/N``
(or ``TESTO_SHARD=I/N``) runs only shard I of N, from the test times in the
cycle's history (``testo_core/services/test_split.py``). Under pytest-xdist the
controller loads the times once and hands them to its workers, so all of them
pick the same tests.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

_RECORD_ENV = "TESTO_RECORD"
# Exit codes after which there is nothing worth recording: interrupted,
# internal error, usage error, no tests collected.
_NOTHING_RAN = frozenset({2, 3, 4, 5})
_TEMP_DIR = pytest.StashKey[Path]()
_SUMMARY = pytest.StashKey[str]()
_RESOURCE_REQUEST = pytest.StashKey["dict[str, Any] | None"]()
_SPEC_ENV = "TESTO_RESOURCE_SPEC"
_SHARD_ENV = "TESTO_SHARD"
_SHARD = pytest.StashKey["tuple[int, int] | None"]()
_SHARD_TIMINGS = pytest.StashKey["dict[str, float]"]()
_SHARD_SUMMARY = pytest.StashKey[str]()
_WORKER_TIMINGS = "testo_shard_timings"


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
    group.addoption(
        "--testo-resource",
        default=None,
        metavar="POOL",
        help="Give each test process its own key from this pool ('resources:' in "
        "testosterone.yaml), in $TESTO_RESOURCE_ID and the testo_resource fixture.",
    )
    group.addoption(
        "--testo-resource-label",
        action="append",
        default=[],
        metavar="LABEL",
        help="Only keys with this label (repeat for several).",
    )
    group.addoption(
        "--testo-resource-per",
        default="worker",
        choices=("worker", "test"),
        help="Hold one key per test process (default), or take one for each test.",
    )
    group.addoption(
        "--testo-resource-wait",
        default="30m",
        metavar="DURATION",
        help="How long to wait for a free key: 90s, 10m, 2h or forever (default: 30m).",
    )
    group.addoption(
        "--testo-shard",
        default=None,
        metavar="I/N",
        help="Run only shard I of N, split so shards take about the same time "
        "(default: $TESTO_SHARD).",
    )
    group.addoption(
        "--testo-timings",
        default=None,
        metavar="CYCLE",
        help="Cycle whose test times --testo-shard uses (default: $TESTO_CYCLE, set by "
        "`testo run`, else the rootdir's name).",
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
    config.stash[_RESOURCE_REQUEST] = _resource_request(config)
    _configure_shard(config)
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
    for key in (_SHARD_SUMMARY, _SUMMARY):
        line = config.stash.get(key, None)
        if line:
            terminalreporter.write_line(line)


# -- resource pools ---------------------------------------------------------------


def _resource_request(config: pytest.Config) -> dict[str, Any] | None:
    """Which pool this session leases from: ``--testo-resource``, else a stage's ``TESTO_RESOURCE_SPEC``."""
    pool = config.getoption("testo_resource")
    if pool:
        return {
            "pool": pool,
            "labels": list(config.getoption("testo_resource_label") or []),
            "per": config.getoption("testo_resource_per"),
            "wait": config.getoption("testo_resource_wait"),
        }
    raw = os.environ.get(_SPEC_ENV)
    if not raw:
        return None
    try:
        sent = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(sent, dict) or sent.get("per") not in ("worker", "test"):
        return None  # per: stage, the stage already holds the key
    return sent


def _is_xdist_controller(config: pytest.Config) -> bool:
    """The process that only hands tests to pytest-xdist workers (it runs none itself)."""
    return not hasattr(config, "workerinput") and getattr(config.option, "dist", "no") != "no"


def _take_key(config: pytest.Config, request: dict[str, Any]) -> Any:
    from testo_core.config.errors import ConfigError
    from testo_core.resources.client import acquire, backend_from_env, default_holder, find_pool
    from testo_core.resources.pools import parse_duration, parse_pool
    from testo_core.resources.store import LeaseError

    try:
        spec = request.get("spec")
        pool = (
            parse_pool(request["pool"], spec)
            if isinstance(spec, dict)
            else find_pool(request["pool"])
        )
        wait = request.get("wait")
        wait_s = wait if isinstance(wait, (int, float)) or wait is None else parse_duration(wait)
        return acquire(
            backend_from_env(),
            pool,
            labels=request.get("labels") or (),
            holder=default_holder(
                stage=str(request.get("stage") or ""),
                worker=os.environ.get("PYTEST_XDIST_WORKER", "main"),
                note="pytest",
            ),
            wait_s=wait_s,
        )
    except (ConfigError, LeaseError, ValueError) as exc:
        pytest.fail(f"testo: no key from pool {request.get('pool')!r}: {exc}", pytrace=False)


def _held(config: pytest.Config, request: dict[str, Any]) -> Iterator[Any]:
    """Take a key, expose it in the environment while it is held, give it back."""
    held = _take_key(config, request)
    saved = {key: os.environ.get(key) for key in held.env()}
    os.environ.update(held.env())
    try:
        yield held
    finally:
        held.release()
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture(scope="session", autouse=True)
def _testo_worker_key(request: pytest.FixtureRequest) -> Iterator[Any]:
    """``per: worker``: this test process's key, taken before its first test."""
    config = request.config
    wanted = config.stash.get(_RESOURCE_REQUEST, None)
    if wanted is None or wanted.get("per") != "worker" or _is_xdist_controller(config):
        yield None
        return
    yield from _held(config, wanted)


@pytest.fixture(autouse=True)
def _testo_test_key(request: pytest.FixtureRequest) -> Iterator[Any]:
    """``per: test``: a key for this test only, so the pool's ``on_take`` runs before each test."""
    config = request.config
    wanted = config.stash.get(_RESOURCE_REQUEST, None)
    if wanted is None or wanted.get("per") != "test":
        yield None
        return
    yield from _held(config, wanted)


@pytest.fixture
def testo_resource(_testo_worker_key: Any, _testo_test_key: Any) -> Any:
    """The key this test holds: ``.id``, ``.data`` (a dict), ``.env()`` and ``.lease``."""
    held = _testo_test_key or _testo_worker_key
    if held is None:
        pytest.fail(
            "testo_resource needs a pool: run pytest with --testo-resource POOL, or from a "
            "testosterone.yaml stage with 'resources:'.",
            pytrace=False,
        )
    return held


# -- shards -----------------------------------------------------------------------


def _configure_shard(config: pytest.Config) -> None:
    raw = config.getoption("testo_shard") or os.environ.get(_SHARD_ENV) or ""
    if not raw.strip():
        config.stash[_SHARD] = None
        return
    from testo_core.services.test_split import (
        SplitError,
        load_test_times,
        parse_shard,
        timings_index,
    )

    try:
        config.stash[_SHARD] = parse_shard(raw)
    except SplitError as exc:
        raise pytest.UsageError(f"--testo-shard: {exc}") from exc
    workerinput = getattr(config, "workerinput", None)
    if workerinput is not None and _WORKER_TIMINGS in workerinput:
        # The controller's times, so every worker keeps the same tests.
        config.stash[_SHARD_TIMINGS] = dict(json.loads(workerinput[_WORKER_TIMINGS]))
        return
    cycle = (
        config.getoption("testo_timings")
        or os.environ.get("TESTO_CYCLE")
        or config.rootpath.name
        or "pytest"
    ).strip()
    server = config.getoption("testo_server") or os.environ.get("TESTO_SERVER_URL") or None
    try:
        times = load_test_times(cycle, server=server, token=os.environ.get("TESTO_API_TOKEN"))
    except Exception as exc:  # noqa: BLE001 - a shard must not guess: another shard may know
        raise pytest.UsageError(
            f"--testo-shard: could not load the test times of cycle {cycle!r}: {exc}"
        ) from exc
    config.stash[_SHARD_TIMINGS] = timings_index(times)
    if _is_xdist_controller(config):  # the workers collect and pick the tests
        timed = sum(1 for t in times if t.median_ms is not None)
        config.stash[_SHARD_SUMMARY] = (
            f"testo: shard {config.stash[_SHARD][0]}/{config.stash[_SHARD][1]} of cycle "
            f"{cycle!r} (times known for {timed} tests)"
        )


@pytest.hookimpl(optionalhook=True)
def pytest_configure_node(node: Any) -> None:
    """pytest-xdist: hand the controller's test times to each worker."""
    timings = node.config.stash.get(_SHARD_TIMINGS, None)
    if timings is not None:
        node.workerinput[_WORKER_TIMINGS] = json.dumps(timings)


@pytest.hookimpl(trylast=True)  # after -k / -m, so the shards split what will run
def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
) -> None:
    shard = config.stash.get(_SHARD, None)
    if shard is None:
        return
    from testo_core.services.test_split import nodeid_names, plan_split

    index, count = shard
    plan = plan_split(
        [item.nodeid for item in items],
        config.stash.get(_SHARD_TIMINGS, {}),
        count,
        names_for=nodeid_names,
    )
    mine = plan.shard(index)
    keep = set(mine.tests)
    selected = [item for item in items if item.nodeid in keep]
    deselected = [item for item in items if item.nodeid not in keep]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected
    if not hasattr(config, "workerinput"):
        about = f", about {mine.estimate_ms / 1000:.1f}s" if plan.timed else ""
        config.stash[_SHARD_SUMMARY] = (
            f"testo: shard {index}/{count} ran {len(selected)} of {plan.total} tests{about} "
            f"(times known for {plan.timed} tests)"
        )
