"""A test retried within one JUnit file counts once, flaky when it passed on retry."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from testo_core.reporting.junit_import import import_junit_reports


def _import(tmp_path: Path, xml: str) -> tuple[object, dict[str, dict]]:
    (tmp_path / "junit.xml").write_text(textwrap.dedent(xml), encoding="utf-8")
    out = tmp_path / "results"
    imported = import_junit_reports(
        target_repo=tmp_path, patterns=("junit.xml",), results_dir=out, tool="junit"
    )
    results = [json.loads(p.read_text()) for p in out.glob("*-result.json")]
    return imported, {r["name"]: r for r in results}


def test_gradle_style_retry_passes_and_is_flaky(tmp_path: Path) -> None:
    imported, by_name = _import(
        tmp_path,
        """\
        <testsuite name="G" tests="3" failures="1">
          <testcase name="retried" classname="G" time="0.1"><failure message="boom">x</failure></testcase>
          <testcase name="retried" classname="G" time="0.1"/>
          <testcase name="ok" classname="G" time="0.1"/>
        </testsuite>
        """,
    )
    assert imported.tests == 2
    assert imported.failed == 0
    assert imported.flaky == 1
    retried = by_name["retried"]
    assert retried["status"] == "passed"
    assert retried["statusDetails"]["flaky"] is True
    assert retried["statusDetails"]["message"] == "Passed on retry. boom"


def test_retry_that_still_fails_counts_once_as_failed(tmp_path: Path) -> None:
    imported, by_name = _import(
        tmp_path,
        """\
        <testsuite name="G">
          <testcase name="t" classname="G"><failure message="one">x</failure></testcase>
          <testcase name="t" classname="G"><failure message="two">x</failure></testcase>
        </testsuite>
        """,
    )
    assert imported.tests == 1
    assert imported.failed == 1
    assert by_name["t"]["statusDetails"]["message"] == "two"
    assert "flaky" not in by_name["t"]["statusDetails"]


def test_surefire_flaky_failure_marks_a_passing_test_flaky(tmp_path: Path) -> None:
    imported, by_name = _import(
        tmp_path,
        """\
        <testsuite name="com.x.FooTest" tests="2">
          <testcase name="retried" classname="com.x.FooTest" time="0.1">
            <flakyFailure message="expected 1" type="java.lang.AssertionError">trace</flakyFailure>
          </testcase>
          <testcase name="ok" classname="com.x.FooTest" time="0.1"/>
        </testsuite>
        """,
    )
    assert imported.tests == 2
    assert imported.flaky == 1
    assert by_name["retried"]["status"] == "passed"
    assert by_name["retried"]["statusDetails"]["flaky"] is True
    assert by_name["retried"]["statusDetails"]["message"] == "Passed on rerun. expected 1"
    assert "statusDetails" not in by_name["ok"]
