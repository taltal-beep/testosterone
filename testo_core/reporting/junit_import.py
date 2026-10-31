"""Convert JUnit XML reports into Allure ``*-result.json`` files.

Runners that don't speak Allure (Jest via ``jest-junit``, Playwright's
``junit`` reporter, Maestro, ``go test`` via go-junit-report, ...) all emit
JUnit XML. A stage lists those files with ``junit_xml`` globs; after the stage
the executor calls :func:`import_junit_reports`, which writes one Allure result
per ``<testcase>`` into the stage's results dir. From there the stage is
counted by :mod:`testo_core.reporting.allure_results` (summaries, health %,
the dashboard) and rendered by every reporter like a pytest/Behave stage.

Status mapping (JUnit has no "broken" of its own):

    <failure>            -> failed
    <error>              -> broken
    <skipped>            -> skipped
    none of the above    -> passed

Other result files among the matches are recognised by their content, not
their name, and read by their own importer, which keeps what JUnit loses:

    Playwright JSON report         -> :mod:`~testo_core.reporting.playwright_import`
    Jest / Vitest JSON report      -> :mod:`~testo_core.reporting.jest_import`
    .NET TRX (``<TestRun>``)       -> :mod:`~testo_core.reporting.trx_import`
    ``go test -json`` output       -> :mod:`~testo_core.reporting.gotest_import`
    Robot Framework ``output.xml`` -> :mod:`~testo_core.reporting.robot_import`
    RSpec JSON (``examples``)      -> :mod:`~testo_core.reporting.rspec_import`
    k6 summary JSON                -> :mod:`~testo_core.reporting.k6_import`
    ``xcresulttool`` JSON          -> :mod:`~testo_core.reporting.xcresult_import`
    Allure ``*-result.json``       -> :mod:`~testo_core.reporting.allure_passthrough`

Any other XML is read as JUnit (which every other runner can write). Android
instrumentation tests (Espresso, UI Automator, Compose) write JUnit XML whose
suites name their ``device``; those results are labelled ``android`` so the
run page offers a ``connectedAndroidTest`` rerun command.

A ``junit`` stage (``testo ingest``) runs no command at all: the executor calls
this without ``not_before`` and derives the stage's returncode from ``failed``.

Only the files a stage's own command wrote are parsed (paths come from the
stage config and stay inside ``target_repo``); expat does not resolve external
entities, so no file or network access happens during parsing.
"""

from __future__ import annotations

import hashlib
import json
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_MAX_TRACE_CHARS = 20_000


@dataclass(frozen=True)
class JunitImportResult:
    files: tuple[Path, ...]
    tests: int
    errors: tuple[str, ...]
    # Cases that ended ``failed`` or ``broken``; what a ``junit`` (ingest) stage's
    # returncode is derived from, since no process exit code exists there.
    failed: int = 0
    # Sum of the per-case ``time`` attributes, in seconds.
    duration_s: float = 0.0
    # Playwright JSON only: tests that passed on a retry, and attachments copied.
    flaky: int = 0
    attachments: int = 0


def _suite_start_ms(suite: ET.Element, fallback_ms: int) -> int:
    stamp = suite.get("timestamp")
    if stamp:
        try:
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            return int(parsed.timestamp() * 1000)
        except ValueError:
            pass
    return fallback_ms


def _seconds_ms(value: str | None) -> int:
    try:
        return max(0, int(round(float(value or 0) * 1000)))
    except (ValueError, OverflowError):
        return 0


def _status(case: ET.Element) -> tuple[str, str | None, str | None]:
    for tag, status in (("failure", "failed"), ("error", "broken"), ("skipped", "skipped")):
        node = case.find(tag)
        if node is None:
            continue
        text = (node.text or "").strip()
        message = node.get("message") or (text.splitlines()[0] if text else None)
        trace = text or None
        if trace and len(trace) > _MAX_TRACE_CHARS:
            trace = trace[:_MAX_TRACE_CHARS] + "\n… (truncated)"
        return status, message, trace
    return "passed", None, None


def _suites(root: ET.Element) -> list[ET.Element]:
    # Every <testsuite> at any depth, the root included (suites nest in some tools'
    # output), depth-first. Each suite then reads only its own direct <testcase>s, so
    # nothing counts twice. A wrapper with <testcase>s of its own acts as a suite too.
    suites = list(root.iter("testsuite"))
    if root.tag != "testsuite" and root.find("testcase") is not None:
        suites.insert(0, root)
    return suites


def _android_device(suite: ET.Element) -> str | None:
    """The device an Android instrumentation suite (Espresso, ``connectedAndroidTest``) ran on."""
    for prop in suite.iterfind("properties/property"):
        if prop.get("name") == "device" and prop.get("value"):
            return prop.get("value")
    return None


def _results_for_root(root: ET.Element, *, path: Path, tool: str, fallback_ms: int) -> list[dict]:
    results: list[dict] = []
    for suite in _suites(root):
        suite_name = suite.get("name") or path.stem
        clock = _suite_start_ms(suite, fallback_ms)
        device = _android_device(suite)
        for case in suite.findall("testcase"):
            name = case.get("name") or "(unnamed)"
            classname = case.get("classname") or suite_name
            full_name = f"{classname}.{name}" if classname else name
            duration = _seconds_ms(case.get("time"))
            status, message, trace = _status(case)
            result: dict = {
                "uuid": str(uuid.uuid4()),
                "historyId": hashlib.sha256(f"{tool}:{full_name}".encode()).hexdigest(),
                "name": name,
                "fullName": full_name,
                "status": status,
                "stage": "finished",
                "start": clock,
                "stop": clock + duration,
                "labels": [
                    {"name": "suite", "value": suite_name},
                    {"name": "testClass", "value": classname},
                    {"name": "framework", "value": "android" if device else tool},
                    {"name": "language", "value": "junit"},
                    *([{"name": "host", "value": device}] if device else []),
                ],
            }
            if message or trace:
                result["statusDetails"] = {
                    k: v for k, v in (("message", message), ("trace", trace)) if v
                }
            results.append(result)
            clock += duration
    return results


@dataclass(frozen=True)
class _FileResults:
    results: list[dict]
    flaky: int = 0
    attachments: int = 0
    notes: tuple[str, ...] = ()


def report_paths(repo: Path, pattern: str) -> list[Path]:
    """What *pattern* names under *repo*: the file itself when it exists (so a name
    with ``[`` or ``*`` in it still works), otherwise the glob's matches, sorted."""
    literal = repo / pattern
    try:
        if literal.is_file():
            return [literal]
    except OSError:
        pass
    return sorted(repo.glob(pattern))


def _results_for_any(
    path: Path, *, tool: str, results_dir: Path, repo: Path
) -> _FileResults | None:
    """One result file's Allure results, by what the file is; ``None`` for files to skip quietly."""
    from testo_core.reporting import allure_passthrough

    if allure_passthrough.is_allure_side_file(path):
        return None
    fallback_ms = int(path.stat().st_mtime * 1000)
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        # UTF-16 with a BOM (.NET and PowerShell write it). expat reads the raw bytes.
        text = raw.decode("utf-16", errors="replace")
    else:
        text = raw.decode("utf-8-sig", errors="replace")
    head = text.lstrip()[:1]
    if head == "<":
        root = ET.fromstring(raw)  # noqa: S314 — stage-owned file, expat ignores external entities
        from testo_core.reporting.robot_import import is_robot_root, robot_results_for_root
        from testo_core.reporting.trx_import import is_trx_root, trx_results_for_root

        if is_trx_root(root):
            return _FileResults(trx_results_for_root(root, tool=tool, fallback_ms=fallback_ms))
        if is_robot_root(root):
            return _FileResults(robot_results_for_root(root, tool=tool, fallback_ms=fallback_ms))
        return _FileResults(_results_for_root(root, path=path, tool=tool, fallback_ms=fallback_ms))
    from testo_core.reporting.gotest_import import gotest_results_for_text, is_gotest_text
    from testo_core.reporting.jest_import import is_jest_report, jest_results_for_report

    if head not in ("{", "["):
        # ``go test -json`` output can start with a build line ("go: downloading ...").
        if is_gotest_text(text):
            return _FileResults(gotest_results_for_text(text, tool=tool, fallback_ms=fallback_ms))
        raise ValueError("not a test result file (neither XML nor JSON)")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        if is_gotest_text(text):
            return _FileResults(gotest_results_for_text(text, tool=tool, fallback_ms=fallback_ms))
        raise ValueError(f"not valid JSON ({exc})") from exc
    if allure_passthrough.is_allure_result(path, data):
        result, copied = allure_passthrough.copy_allure_result(
            path, data, results_dir=results_dir, tool=tool
        )
        return _FileResults([result], attachments=copied)
    if is_jest_report(data):
        results = jest_results_for_report(data, tool=tool, root=repo, fallback_ms=fallback_ms)
        flaky = sum(1 for r in results if (r.get("statusDetails") or {}).get("flaky"))
        return _FileResults(results, flaky=flaky)
    from testo_core.reporting.k6_import import is_k6_summary, k6_results_for_summary
    from testo_core.reporting.rspec_import import is_rspec_report, rspec_results_for_report
    from testo_core.reporting.xcresult_import import (
        is_xcresult_report,
        xcresult_results_for_report,
    )

    if is_rspec_report(data):
        return _FileResults(rspec_results_for_report(data, tool=tool, fallback_ms=fallback_ms))
    if is_k6_summary(data):
        return _FileResults(k6_results_for_summary(data, tool=tool, fallback_ms=fallback_ms))
    if is_xcresult_report(data):
        results = xcresult_results_for_report(data, tool=tool, fallback_ms=fallback_ms)
        flaky = sum(1 for r in results if (r.get("statusDetails") or {}).get("flaky"))
        return _FileResults(results, flaky=flaky)
    if isinstance(data, dict) and isinstance(data.get("suites"), list):
        from testo_core.reporting.playwright_import import playwright_results_for_file

        parsed = playwright_results_for_file(
            path, tool=tool, results_dir=results_dir, attachments_root=repo
        )
        return _FileResults(parsed.results, parsed.flaky, parsed.attachments, parsed.notes)
    if is_gotest_text(text):  # a single-event go test file is valid JSON too
        return _FileResults(gotest_results_for_text(text, tool=tool, fallback_ms=fallback_ms))
    raise ValueError(
        "not a known JSON report (Playwright, Jest/Vitest, RSpec, k6, xcresulttool,"
        " go test -json or an Allure result)"
    )


def import_junit_reports(
    *,
    target_repo: Path,
    patterns: tuple[str, ...],
    results_dir: Path,
    tool: str = "command",
    not_before: float | None = None,
    first_match_only: bool = False,
) -> JunitImportResult:
    """Convert every result file matching ``patterns`` (JUnit XML or another known format) into Allure results.

    ``first_match_only`` reads only the files of the first pattern that
    matches anything, for adapters that list one report in several formats
    (Playwright: its JSON report, else its JUnit report) and must not count
    the same tests twice. Attachments a Playwright report points to are copied
    only from inside ``target_repo``.

    ``not_before`` (epoch seconds, the stage start) skips files older than the
    stage, so a stale report left by an earlier run is never counted as this
    run's result. A malformed file is reported in ``errors`` and skipped; it
    never fails the stage on its own (the process exit code already does).
    """
    repo = target_repo.expanduser().resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for pattern in patterns:
        for match in report_paths(repo, pattern):
            resolved = match.resolve()
            if not resolved.is_file() or repo not in resolved.parents:
                continue
            if not_before is not None and resolved.stat().st_mtime < not_before - 1:
                continue
            if resolved not in files:
                files.append(resolved)
        if first_match_only and files:
            break

    tests = 0
    failed = 0
    duration_ms = 0
    flaky = 0
    attachments = 0
    errors: list[str] = []
    for path in files:
        try:
            parsed = _results_for_any(path, tool=tool, results_dir=results_dir, repo=repo)
        except (ET.ParseError, OSError, ValueError, UnicodeDecodeError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 — one odd file must not lose the others
            errors.append(f"{path.name}: could not read it ({type(exc).__name__}: {exc})")
            continue
        if parsed is None:  # an Allure folder's container, attachment or settings file
            continue
        results = parsed.results
        flaky += parsed.flaky
        attachments += parsed.attachments
        errors += [f"{path.name}: {note}" for note in parsed.notes]
        for result in results:
            out = results_dir / f"{result['uuid']}-result.json"
            out.write_text(json.dumps(result), encoding="utf-8")
            if result.get("status") in ("failed", "broken"):
                failed += 1
            duration_ms += max(0, int(result.get("stop") or 0) - int(result.get("start") or 0))
        tests += len(results)
    return JunitImportResult(
        files=tuple(files),
        tests=tests,
        errors=tuple(errors),
        failed=failed,
        duration_s=duration_ms / 1000,
        flaky=flaky,
        attachments=attachments,
    )
