"""Tests for archived run diff (per-test Allure case map)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from testo_core.repository.models import ReportArchive
from testo_core.services.report_archive import build_cycle_zip_bytes
from testo_core.services.report_archive_diff import diff_archives, parse_archive_uuid


def _plan_with_result(root: Path, plan: str, result_payload: dict) -> bytes:
    plan_dir = root / plan
    plan_dir.mkdir(parents=True)
    (plan_dir / "events.ndjson").write_text("{}\n", encoding="utf-8")
    (plan_dir / "plan_result.json").write_text(
        json.dumps({"plan": plan, "exit_code": 0, "duration_s": 1.0}),
        encoding="utf-8",
    )
    res = plan_dir / "st" / "allure-results" / "pytest"
    res.mkdir(parents=True)
    (res / "t-result.json").write_text(json.dumps(result_payload), encoding="utf-8")
    blob, _summary, _ = build_cycle_zip_bytes(root, plan)
    return blob


def test_diff_archives_regression_and_fix(tmp_path: Path) -> None:
    plan = "same-cycle"
    base_blob = _plan_with_result(
        tmp_path / "b",
        plan,
        {"historyId": "hid1", "status": "passed", "name": "t", "start": 0, "stop": 1000},
    )
    cur_blob = _plan_with_result(
        tmp_path / "c",
        plan,
        {"historyId": "hid1", "status": "failed", "name": "t", "start": 0, "stop": 500},
    )

    bid, cid = uuid.uuid4(), uuid.uuid4()
    baseline = ReportArchive(
        id=bid,
        cycle_name=plan,
        exit_code=0,
        summary_json={},
        artifact_bytes=base_blob,
        total_tests=1,
        passed=1,
        failed=0,
    )
    current = ReportArchive(
        id=cid,
        cycle_name=plan,
        exit_code=1,
        summary_json={},
        artifact_bytes=cur_blob,
        total_tests=1,
        passed=0,
        failed=1,
    )

    td = tmp_path / "diffwork"
    td.mkdir()
    changes, metrics = diff_archives(baseline=baseline, current=current, tmp=td)
    kinds = {c.kind for c in changes}
    assert "regression" in kinds
    reg = next(c for c in changes if c.kind == "regression")
    assert reg.group == "(ungrouped)"
    assert metrics["baseline_id"] == str(bid)
    assert metrics["current_id"] == str(cid)

    fix_blob = _plan_with_result(
        tmp_path / "d",
        plan,
        {"historyId": "hid1", "status": "passed", "name": "t", "start": 0, "stop": 100},
    )
    fixed = ReportArchive(
        id=uuid.uuid4(),
        cycle_name=plan,
        exit_code=0,
        summary_json={},
        artifact_bytes=fix_blob,
    )
    td2 = tmp_path / "diffwork2"
    td2.mkdir()
    changes2, _ = diff_archives(baseline=current, current=fixed, tmp=td2)
    assert any(c.kind == "fix" for c in changes2)


def test_parse_archive_uuid() -> None:
    u = uuid.uuid4()
    assert parse_archive_uuid(str(u)) == u
    assert parse_archive_uuid("not-a-uuid") is None


def test_diff_archives_group_from_package_label(tmp_path: Path) -> None:
    plan = "pkg-cycle"
    labels = [{"name": "package", "value": "com.acme.tests"}]
    base_blob = _plan_with_result(
        tmp_path / "g1",
        plan,
        {
            "historyId": "hid2",
            "status": "passed",
            "name": "t2",
            "labels": labels,
            "start": 0,
            "stop": 100,
        },
    )
    cur_blob = _plan_with_result(
        tmp_path / "g2",
        plan,
        {
            "historyId": "hid2",
            "status": "failed",
            "name": "t2",
            "labels": labels,
            "start": 0,
            "stop": 200,
        },
    )
    baseline = ReportArchive(
        id=uuid.uuid4(),
        cycle_name=plan,
        exit_code=0,
        summary_json={},
        artifact_bytes=base_blob,
    )
    current = ReportArchive(
        id=uuid.uuid4(),
        cycle_name=plan,
        exit_code=1,
        summary_json={},
        artifact_bytes=cur_blob,
    )
    td = tmp_path / "diffpkg"
    td.mkdir()
    changes, _ = diff_archives(baseline=baseline, current=current, tmp=td)
    reg = next(c for c in changes if c.kind == "regression")
    assert reg.group == "com.acme.tests"
