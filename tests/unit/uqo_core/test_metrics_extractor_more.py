"""More coverage for ``uqo_core.metrics_extractor``."""

from __future__ import annotations

import json
from pathlib import Path

from uqo_core.metrics_extractor import (
    extract_from_report_dir,
    extract_from_summary_json,
    write_manual_locust_results_json,
)


def test_extract_from_summary_json_parses_duration(tmp_path: Path) -> None:
    p = tmp_path / "summary.json"
    p.write_text(
        json.dumps(
            {
                "statistic": {"passed": 2, "failed": 1, "broken": 0, "skipped": 0, "unknown": 0, "total": 3},
                "time": {"sumDuration": 1234},
            }
        ),
        encoding="utf-8",
    )
    m = extract_from_summary_json(summary_path=p)
    assert m is not None
    assert m.total_tests == 3
    assert m.duration_ms == 1234


def test_extract_from_report_dir_widgets(tmp_path: Path) -> None:
    rep = tmp_path / "rep"
    (rep / "widgets").mkdir(parents=True)
    (rep / "widgets" / "summary.json").write_text(
        json.dumps({"statistic": {"passed": 1, "total": 1}, "time": {"duration": 10}}),
        encoding="utf-8",
    )
    m = extract_from_report_dir(report_dir=rep)
    assert m is not None
    assert m.passed == 1


def test_write_manual_locust_results_json(tmp_path: Path) -> None:
    out = write_manual_locust_results_json(tmp_path, audit_run_id="a", phase_returncodes=[0, 1])
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["framework"] == "locust"

