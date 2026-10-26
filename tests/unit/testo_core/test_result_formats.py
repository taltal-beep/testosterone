"""Runners' own result formats, recognised by content: Jest/Vitest JSON, TRX, go test -json, Robot, Allure."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from testo_core.reporting.junit_import import import_junit_reports

pytestmark = [pytest.mark.unit, pytest.mark.tier_fast]

JEST = {
    "numTotalTests": 5,
    "startTime": 1_760_000_000_000,
    "success": False,
    "testResults": [
        {
            "name": "/ci/work/app/src/cart.test.js",
            "status": "failed",
            "startTime": 1_760_000_000_100,
            "message": "",
            "assertionResults": [
                {
                    "ancestorTitles": ["cart", "totals"],
                    "title": "adds tax",
                    "fullName": "cart totals adds tax",
                    "status": "passed",
                    "duration": 12,
                    "failureMessages": [],
                },
                {
                    "ancestorTitles": ["cart"],
                    "title": "rejects negative",
                    "status": "failed",
                    "duration": 5,
                    "failureMessages": [
                        "Error: expect(received).toBe(expected)\n    at cart.test.js:9"
                    ],
                },
                {"ancestorTitles": [], "title": "later", "status": "todo", "failureMessages": []},
                {
                    "ancestorTitles": [],
                    "title": "retried",
                    "status": "passed",
                    "duration": 3,
                    "failureMessages": [],
                    "retryReasons": ["Error: timeout"],
                },
            ],
        },
        {
            "name": "/ci/work/app/src/broken.test.js",
            "status": "failed",
            "message": "SyntaxError: Unexpected token",
            "assertionResults": [],
        },
    ],
}

TRX = """<?xml version="1.0" encoding="utf-8"?>
<TestRun id="1" name="run" xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">
  <Times start="2026-10-26T10:00:00.0000000+00:00" />
  <Results>
    <UnitTestResult testId="a" testName="Shop.Tests.CartTests.AddsTax" outcome="Passed" duration="00:00:00.0120000" />
    <UnitTestResult testId="b" testName="Shop.Tests.CartTests.RejectsNegative" outcome="Failed" duration="00:00:01.5000000">
      <Output><ErrorInfo><Message>Assert.Equal() Failure</Message><StackTrace>at CartTests.cs:line 9</StackTrace></ErrorInfo></Output>
    </UnitTestResult>
    <UnitTestResult testId="c" testName="Shop.Tests.CartTests.Later" outcome="NotExecuted" duration="00:00:00" />
    <UnitTestResult testId="d" testName="Rows" outcome="Failed">
      <InnerResults>
        <UnitTestResult testId="d" testName="Rows(1)" outcome="Passed" duration="00:00:00.0010000" />
        <UnitTestResult testId="d" testName="Rows(2)" outcome="Timeout" duration="00:00:00.0010000" />
      </InnerResults>
    </UnitTestResult>
  </Results>
  <TestDefinitions>
    <UnitTest id="a" name="AddsTax"><TestMethod className="Shop.Tests.CartTests" name="AddsTax" /></UnitTest>
    <UnitTest id="b" name="RejectsNegative"><TestMethod className="Shop.Tests.CartTests" name="RejectsNegative" /></UnitTest>
    <UnitTest id="c" name="Later"><TestMethod className="Shop.Tests.CartTests" name="Later" /></UnitTest>
    <UnitTest id="d" name="Rows"><TestMethod className="Shop.Tests.RowTests" name="Rows" /></UnitTest>
  </TestDefinitions>
</TestRun>
"""


def _go_lines() -> str:
    events = [
        {"Action": "start", "Package": "example.com/shop"},
        {"Action": "run", "Package": "example.com/shop", "Test": "TestCart"},
        {"Action": "run", "Package": "example.com/shop", "Test": "TestCart/tax"},
        {"Action": "pass", "Package": "example.com/shop", "Test": "TestCart/tax", "Elapsed": 0.01},
        {"Action": "run", "Package": "example.com/shop", "Test": "TestCart/negative"},
        {
            "Action": "output",
            "Package": "example.com/shop",
            "Test": "TestCart/negative",
            "Output": "=== RUN   TestCart/negative\n",
        },
        {
            "Action": "output",
            "Package": "example.com/shop",
            "Test": "TestCart/negative",
            "Output": "    cart_test.go:21: want error, got nil\n",
        },
        {
            "Action": "fail",
            "Package": "example.com/shop",
            "Test": "TestCart/negative",
            "Elapsed": 0.02,
        },
        {"Action": "fail", "Package": "example.com/shop", "Test": "TestCart", "Elapsed": 0.03},
        {"Action": "skip", "Package": "example.com/shop", "Test": "TestLater", "Elapsed": 0},
        {"Action": "fail", "Package": "example.com/shop", "Elapsed": 0.5},
        {
            "Action": "output",
            "Package": "example.com/broken",
            "Output": "# example.com/broken\nbroken.go:3: undefined: x\n",
        },
        {"Action": "fail", "Package": "example.com/broken", "Elapsed": 0},
    ]
    return "go: downloading something\n" + "\n".join(json.dumps(e) for e in events) + "\n"


ROBOT = """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.1" generated="2026-10-26T10:00:00.000000">
  <suite id="s1" name="Tests">
    <suite id="s1-s1" name="Login">
      <test id="s1-s1-t1" name="Valid Login">
        <tag>smoke</tag>
        <status status="PASS" start="2026-10-26T10:00:01.000000" elapsed="1.250"/>
      </test>
      <test id="s1-s1-t2" name="Wrong Password">
        <status status="FAIL" start="2026-10-26T10:00:03.000000" elapsed="0.5">Page should have contained 'Error'</status>
      </test>
      <test id="s1-s1-t3" name="Later">
        <status status="SKIP" starttime="20261026 10:00:04.000" endtime="20261026 10:00:04.100">Not ready</status>
      </test>
    </suite>
  </suite>
</robot>
"""


def _import(
    tmp_path: Path, files: dict[str, str | bytes], pattern: str = "out/*", tool: str = "junit"
):
    repo = tmp_path / "repo"
    for rel, content in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    results_dir = tmp_path / "results"
    imported = import_junit_reports(
        target_repo=repo, patterns=(pattern,), results_dir=results_dir, tool=tool
    )
    results = {}
    for path in results_dir.glob("*-result.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        results[data["fullName"]] = data
    return imported, results, results_dir


def _label(result: dict, name: str) -> str | None:
    return next((lab["value"] for lab in result["labels"] if lab["name"] == name), None)


def test_jest_json(tmp_path: Path) -> None:
    imported, results, _ = _import(tmp_path, {"out/jest.json": json.dumps(JEST)})

    assert imported.errors == ()
    assert (imported.tests, imported.failed) == (5, 2)
    assert {k: v["status"] for k, v in results.items()} == {
        "cart.test.js › cart › totals › adds tax": "passed",
        "cart.test.js › cart › rejects negative": "failed",
        "cart.test.js › later": "skipped",
        "cart.test.js › retried": "passed",
        "broken.test.js › (test file failed to run)": "broken",
    }
    failed = results["cart.test.js › cart › rejects negative"]
    assert failed["statusDetails"]["message"] == "Error: expect(received).toBe(expected)"
    assert _label(failed, "framework") == "jest"
    assert _label(failed, "subSuite") == "cart"
    assert results["cart.test.js › retried"]["statusDetails"]["flaky"] is True
    broken = results["broken.test.js › (test file failed to run)"]
    assert broken["statusDetails"]["message"] == "SyntaxError: Unexpected token"


def test_jest_paths_inside_the_repo_are_relative_to_it(tmp_path: Path) -> None:
    repo = (tmp_path / "repo").resolve()
    report = json.loads(json.dumps(JEST))
    report["testResults"][0]["name"] = str(repo / "src" / "cart.test.js")
    report["testResults"] = report["testResults"][:1]
    _, results, _ = _import(tmp_path, {"out/jest.json": json.dumps(report)})
    assert "src/cart.test.js › later" in results


def test_vitest_json_is_labelled_vitest(tmp_path: Path) -> None:
    report = json.loads(json.dumps(JEST))
    for case in report["testResults"][0]["assertionResults"]:
        case["meta"] = {}
    _, results, _ = _import(tmp_path, {"out/vitest.json": json.dumps(report)})
    assert _label(results["cart.test.js › later"], "framework") == "vitest"


def test_trx(tmp_path: Path) -> None:
    imported, results, _ = _import(tmp_path, {"out/results.trx": TRX})

    assert imported.errors == ()
    assert {k: v["status"] for k, v in results.items()} == {
        "Shop.Tests.CartTests.AddsTax": "passed",
        "Shop.Tests.CartTests.RejectsNegative": "failed",
        "Shop.Tests.CartTests.Later": "skipped",
        "Shop.Tests.RowTests.Rows(1)": "passed",
        "Shop.Tests.RowTests.Rows(2)": "broken",
    }
    failed = results["Shop.Tests.CartTests.RejectsNegative"]
    assert failed["name"] == "RejectsNegative"
    assert failed["stop"] - failed["start"] == 1500
    assert failed["statusDetails"]["message"] == "Assert.Equal() Failure"
    assert "CartTests.cs:line 9" in failed["statusDetails"]["trace"]
    assert _label(failed, "framework") == "dotnet"
    assert _label(failed, "testClass") == "Shop.Tests.CartTests"


def test_trx_with_a_byte_order_mark(tmp_path: Path) -> None:
    imported, results, _ = _import(tmp_path, {"out/results.trx": b"\xef\xbb\xbf" + TRX.encode()})
    assert imported.errors == ()
    assert len(results) == 5


def test_go_test_json(tmp_path: Path) -> None:
    imported, results, _ = _import(tmp_path, {"out/go-test.json": _go_lines()})

    assert imported.errors == ()
    # The parent TestCart is left out: its failing subtest already counts.
    assert {k: v["status"] for k, v in results.items()} == {
        "example.com/shop.TestCart/tax": "passed",
        "example.com/shop.TestCart/negative": "failed",
        "example.com/shop.TestLater": "skipped",
        "example.com/broken.(package failed)": "broken",
    }
    failed = results["example.com/shop.TestCart/negative"]
    assert failed["name"] == "negative"
    assert failed["statusDetails"]["message"] == "cart_test.go:21: want error, got nil"
    assert "=== RUN" not in failed["statusDetails"]["trace"]
    assert _label(failed, "framework") == "go"
    assert (
        "undefined: x" in results["example.com/broken.(package failed)"]["statusDetails"]["trace"]
    )


def test_go_parent_that_failed_on_its_own_is_kept(tmp_path: Path) -> None:
    events = [
        {"Action": "pass", "Package": "p", "Test": "TestX/a", "Elapsed": 0.1},
        {
            "Action": "output",
            "Package": "p",
            "Test": "TestX",
            "Output": "    x_test.go:5: setup failed\n",
        },
        {"Action": "fail", "Package": "p", "Test": "TestX", "Elapsed": 0.2},
    ]
    text = "\n".join(json.dumps(e) for e in events)
    _, results, _ = _import(tmp_path, {"out/go.jsonl": text})
    assert {k: v["status"] for k, v in results.items()} == {
        "p.TestX/a": "passed",
        "p.TestX": "failed",
    }


def test_robot_output_xml(tmp_path: Path) -> None:
    imported, results, _ = _import(tmp_path, {"out/output.xml": ROBOT})

    assert imported.errors == ()
    assert {k: v["status"] for k, v in results.items()} == {
        "Tests.Login.Valid Login": "passed",
        "Tests.Login.Wrong Password": "failed",
        "Tests.Login.Later": "skipped",
    }
    passed = results["Tests.Login.Valid Login"]
    assert passed["stop"] - passed["start"] == 1250
    assert _label(passed, "tag") == "smoke"
    assert _label(passed, "framework") == "robot"
    assert results["Tests.Login.Wrong Password"]["statusDetails"]["message"] == (
        "Page should have contained 'Error'"
    )
    later = results["Tests.Login.Later"]
    assert later["stop"] - later["start"] == 100


def test_allure_results_folder(tmp_path: Path) -> None:
    result = {
        "uuid": "u1",
        "name": "adds tax",
        "fullName": "shop.CartTest.addsTax",
        "status": "failed",
        "start": 1000,
        "stop": 1500,
        "statusDetails": {"message": "expected 2"},
        "steps": [
            {"name": "open", "attachments": [{"name": "shot", "source": "s1-attachment.png"}]}
        ],
        "labels": [{"name": "framework", "value": "junit5"}],
    }
    files = {
        "allure-results/u1-result.json": json.dumps(result),
        "allure-results/s1-attachment.png": b"PNG",
        "allure-results/c1-container.json": json.dumps({"uuid": "c1", "children": ["u1"]}),
        "allure-results/environment.properties": "os=linux",
        "allure-results/categories.json": "[]",
    }
    imported, results, results_dir = _import(tmp_path, files, pattern="allure-results/*")

    assert imported.errors == ()
    assert (imported.tests, imported.failed, imported.attachments) == (1, 1, 1)
    stored = results["shop.CartTest.addsTax"]
    assert _label(stored, "framework") == "junit5"
    assert (results_dir / "s1-attachment.png").read_bytes() == b"PNG"


def test_unknown_files_are_reported_not_fatal(tmp_path: Path) -> None:
    imported, results, _ = _import(tmp_path, {"out/notes.txt": "hello", "out/odd.json": '{"x": 1}'})
    assert results == {}
    assert len(imported.errors) == 2
    assert any("neither XML nor JSON" in e for e in imported.errors)


def test_junit_still_works_next_to_other_formats(tmp_path: Path) -> None:
    junit = '<testsuite name="s"><testcase classname="a.B" name="c"/></testsuite>'
    imported, results, _ = _import(
        tmp_path,
        {"out/junit.xml": junit, "out/results.trx": TRX, "out/jest.json": json.dumps(JEST)},
    )
    assert imported.tests == 11
    assert "a.B.c" in results
