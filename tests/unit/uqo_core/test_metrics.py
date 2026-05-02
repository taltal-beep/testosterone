"""Tests for ``uqo_core.metrics`` parsing."""

from __future__ import annotations

import json
from pathlib import Path

from uqo_core.metrics import RunMetrics, parse_allure_results_dir, write_metrics_json


def test_parse_allure_results_dir_recurse(tmp_path: Path) -> None:
    sub = tmp_path / "pytest"
    sub.mkdir()
    p = sub / "abc-result.json"
    p.write_text(json.dumps({"status": "passed", "start": 1, "stop": 5}), encoding="utf-8")
    m = parse_allure_results_dir(tmp_path)
    assert isinstance(m, RunMetrics)
    assert m.total_tests == 1
    assert m.passed == 1


def test_write_metrics_json_roundtrip(tmp_path: Path) -> None:
    m = RunMetrics(
        timestamp=1,
        total_tests=2,
        passed=1,
        failed=1,
        broken=0,
        skipped=0,
        unknown=0,
        duration_ms=100,
        run_id="rid",
    )
    out = write_metrics_json(m, out_path=tmp_path / "m.json")
    assert out.read_text(encoding="utf-8").count("total_tests") >= 1

