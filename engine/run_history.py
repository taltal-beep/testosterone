from __future__ import annotations

import json
import shutil
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .metrics import parse_allure_results_dir
from .report_generator import (
    STATIC_ALLURE_HTML,
    STATIC_ALLURE_REPORT_DIR,
    STATIC_ALLURE_UNIFIED_DIR,
    STATIC_BEHAVE_DIR,
    STATIC_LOCUST_HTML,
)
from .runners import RunResult

ORCHESTRATOR_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ORCHESTRATOR_ROOT / "artifacts" / "uqo_run_history.sqlite"
STATIC_HISTORY_ROOT = ORCHESTRATOR_ROOT / "static" / "history"


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    created_at: float
    started_at: float
    finished_at: float
    test_kind: str
    returncode: int
    wall_duration_ms: float
    metrics_duration_ms: int | None
    total_tests: int | None
    passed: int | None
    avg_case_ms: float | None
    health_pct: float | None
    target_repo: str | None
    snapshot_dir: str | None
    audit_json: str | None


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    p = db_path or DEFAULT_DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                started_at REAL NOT NULL,
                finished_at REAL NOT NULL,
                test_kind TEXT NOT NULL,
                returncode INTEGER NOT NULL,
                wall_duration_ms REAL NOT NULL,
                metrics_duration_ms INTEGER,
                total_tests INTEGER,
                passed INTEGER,
                failed INTEGER,
                avg_case_ms REAL,
                health_pct REAL,
                target_repo TEXT,
                snapshot_dir TEXT,
                audit_json TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _snapshot_reports(*, run_id: str, artifacts_root: Path) -> Path | None:
    """Copy current static mirrors into ``artifacts/history/<run_id>/``."""
    dest = artifacts_root.expanduser().resolve() / "history" / run_id
    try:
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        if STATIC_ALLURE_UNIFIED_DIR.is_dir() and (STATIC_ALLURE_UNIFIED_DIR / "index.html").is_file():
            ar_dest = dest / "allure_report"
            if ar_dest.exists():
                shutil.rmtree(ar_dest)
            shutil.copytree(STATIC_ALLURE_UNIFIED_DIR, ar_dest)
        elif STATIC_ALLURE_REPORT_DIR.is_dir() and (STATIC_ALLURE_REPORT_DIR / "index.html").is_file():
            ar_dest = dest / "allure_report"
            if ar_dest.exists():
                shutil.rmtree(ar_dest)
            shutil.copytree(STATIC_ALLURE_REPORT_DIR, ar_dest)
        elif STATIC_ALLURE_HTML.is_file():
            shutil.copy2(STATIC_ALLURE_HTML, dest / "allure_report.html")
        if STATIC_LOCUST_HTML.is_file():
            shutil.copy2(STATIC_LOCUST_HTML, dest / "locust_report.html")
        if STATIC_BEHAVE_DIR.is_dir() and any(STATIC_BEHAVE_DIR.iterdir()):
            shutil.copytree(STATIC_BEHAVE_DIR, dest / "behave")

        # Also mirror into ``./static/history/<run_id>/`` so the UI can open historical reports
        # via Streamlit static serving (no extra HTTP server needed).
        try:
            static_dest = (STATIC_HISTORY_ROOT / run_id).resolve()
            if static_dest.exists():
                shutil.rmtree(static_dest)
            static_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(dest, static_dest)
        except OSError:
            pass
        return dest
    except OSError:
        return None


@dataclass(frozen=True)
class RunSessionView:
    """UI-friendly grouped run session with available report links."""

    run_id: str
    created_at: float
    returncode: int
    health_pct: float | None
    total_tests: int | None
    passed: int | None
    links_under_static: dict[str, str]


def list_run_sessions(*, limit: int = 30, db_path: Path | None = None) -> list[RunSessionView]:
    """
    Presentation-friendly run sessions grouped by the persisted ``run_id``.

    Also computes which historical reports are openable via Streamlit static serving by
    checking ``./static/history/<run_id>/``.
    """
    out: list[RunSessionView] = []
    for r in list_recent_runs(limit=limit, db_path=db_path):
        links: dict[str, str] = {}
        base = STATIC_HISTORY_ROOT / r.run_id
        # Prefer directory-based Allure output
        if (base / "allure_report" / "index.html").is_file():
            links["allure"] = f"history/{r.run_id}/allure_report/index.html"
            links["pytest"] = links["allure"]
        elif (base / "allure_report.html").is_file():
            links["allure"] = f"history/{r.run_id}/allure_report.html"
            links["pytest"] = links["allure"]
        if (base / "locust_report.html").is_file():
            links["locust"] = f"history/{r.run_id}/locust_report.html"
        if (base / "behave" / "index.html").is_file():
            links["behavex"] = f"history/{r.run_id}/behave/index.html"

        out.append(
            RunSessionView(
                run_id=r.run_id,
                created_at=r.created_at,
                returncode=r.returncode,
                health_pct=r.health_pct,
                total_tests=r.total_tests,
                passed=r.passed,
                links_under_static=links,
            )
        )
    return out


def record_completed_run(
    *,
    rr: RunResult,
    artifacts_root: Path,
    test_kind: str,
    audit_health_pct: float | None = None,
    db_path: Path | None = None,
) -> None:
    """Persist metadata and snapshot HTML after a run completes."""
    init_schema(db_path)
    env = rr.command.env
    run_id = env.get("UQO_AUDIT_RUN_ID") or env.get("UQO_RUN_ID")
    if not run_id:
        return

    ar = artifacts_root.expanduser().resolve()
    results_dir = ar / "allure-results"
    m = None
    try:
        if results_dir.is_dir():
            m = parse_allure_results_dir(results_dir)
    except Exception:
        m = None

    wall_ms = max(0.0, (rr.finished_at - rr.started_at) * 1000.0)
    metrics_ms = int(m.duration_ms) if m else None
    total_t = int(m.total_tests) if m else None
    passed = int(m.passed) if m else None
    failed = int(m.failed) if m else None
    avg_case = None
    if m and m.total_tests > 0:
        avg_case = float(m.duration_ms) / float(m.total_tests)

    health = rr.audit_health_pct if rr.audit_mode else audit_health_pct
    if health is None and m and m.total_tests > 0:
        health = (m.passed / m.total_tests) * 100.0

    audit_blob: str | None = None
    if rr.audit_mode:
        audit_blob = json.dumps(
            {
                "partial": rr.audit_partial_success,
                "phases": list(rr.audit_phase_returncodes),
                "health_pct": rr.audit_health_pct,
            }
        )

    snap = _snapshot_reports(run_id=run_id, artifacts_root=ar)
    snap_rel = str(snap.relative_to(ORCHESTRATOR_ROOT)) if snap else None

    target_repo = str(rr.command.cwd)

    conn = _connect(db_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO runs (
                run_id, created_at, started_at, finished_at, test_kind, returncode,
                wall_duration_ms, metrics_duration_ms, total_tests, passed, failed,
                avg_case_ms, health_pct, target_repo, snapshot_dir, audit_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                time.time(),
                rr.started_at,
                rr.finished_at,
                test_kind,
                int(rr.returncode),
                wall_ms,
                metrics_ms,
                total_t,
                passed,
                failed,
                avg_case,
                float(health) if health is not None else None,
                target_repo,
                snap_rel,
                audit_blob,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_recent_runs(*, limit: int = 30, db_path: Path | None = None) -> list[RunRecord]:
    init_schema(db_path)
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            SELECT * FROM runs ORDER BY created_at DESC LIMIT ?
            """,
            (int(limit),),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    out: list[RunRecord] = []
    for r in rows:
        out.append(
            RunRecord(
                run_id=str(r["run_id"]),
                created_at=float(r["created_at"]),
                started_at=float(r["started_at"]),
                finished_at=float(r["finished_at"]),
                test_kind=str(r["test_kind"]),
                returncode=int(r["returncode"]),
                wall_duration_ms=float(r["wall_duration_ms"]),
                metrics_duration_ms=int(r["metrics_duration_ms"]) if r["metrics_duration_ms"] is not None else None,
                total_tests=int(r["total_tests"]) if r["total_tests"] is not None else None,
                passed=int(r["passed"]) if r["passed"] is not None else None,
                avg_case_ms=float(r["avg_case_ms"]) if r["avg_case_ms"] is not None else None,
                health_pct=float(r["health_pct"]) if r["health_pct"] is not None else None,
                target_repo=str(r["target_repo"]) if r["target_repo"] else None,
                snapshot_dir=str(r["snapshot_dir"]) if r["snapshot_dir"] else None,
                audit_json=str(r["audit_json"]) if r["audit_json"] else None,
            )
        )
    return out


def get_run(*, run_id: str, db_path: Path | None = None) -> RunRecord | None:
    init_schema(db_path)
    conn = _connect(db_path)
    try:
        cur = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        r = cur.fetchone()
    finally:
        conn.close()
    if r is None:
        return None
    return RunRecord(
        run_id=str(r["run_id"]),
        created_at=float(r["created_at"]),
        started_at=float(r["started_at"]),
        finished_at=float(r["finished_at"]),
        test_kind=str(r["test_kind"]),
        returncode=int(r["returncode"]),
        wall_duration_ms=float(r["wall_duration_ms"]),
        metrics_duration_ms=int(r["metrics_duration_ms"]) if r["metrics_duration_ms"] is not None else None,
        total_tests=int(r["total_tests"]) if r["total_tests"] is not None else None,
        passed=int(r["passed"]) if r["passed"] is not None else None,
        avg_case_ms=float(r["avg_case_ms"]) if r["avg_case_ms"] is not None else None,
        health_pct=float(r["health_pct"]) if r["health_pct"] is not None else None,
        target_repo=str(r["target_repo"]) if r["target_repo"] else None,
        snapshot_dir=str(r["snapshot_dir"]) if r["snapshot_dir"] else None,
        audit_json=str(r["audit_json"]) if r["audit_json"] else None,
    )


def compare_latest_two(*, db_path: Path | None = None) -> dict[str, Any] | None:
    """Compare the two most recent runs (by ``created_at``)."""
    recent = list_recent_runs(limit=2, db_path=db_path)
    if len(recent) < 2:
        return None
    cur, prev = recent[0], recent[1]

    def _delta(a: float | None, b: float | None) -> float | None:
        if a is None or b is None:
            return None
        return a - b

    d_wall = _delta(cur.wall_duration_ms, prev.wall_duration_ms)
    d_metrics = None
    if cur.metrics_duration_ms is not None and prev.metrics_duration_ms is not None:
        d_metrics = float(cur.metrics_duration_ms - prev.metrics_duration_ms)
    d_avg = _delta(cur.avg_case_ms, prev.avg_case_ms)

    lines: list[str] = []
    if d_metrics is not None:
        if d_metrics > 0:
            lines.append(
                f"Allure aggregate result span **increased by {d_metrics:.0f} ms** vs the previous run "
                f"(`{prev.run_id[:8]}…`)."
            )
        elif d_metrics < 0:
            lines.append(
                f"Allure aggregate result span **decreased by {-d_metrics:.0f} ms** vs the previous run "
                f"(`{prev.run_id[:8]}…`)."
            )
        else:
            lines.append("Allure aggregate result span is **unchanged** vs the previous run.")
    if d_avg is not None and (cur.total_tests or 0) > 0:
        if d_avg > 0:
            lines.append(
                f"Average time per Allure test case **increased by {d_avg:.2f} ms** (approx. latency per case)."
            )
        elif d_avg < 0:
            lines.append(
                f"Average time per Allure test case **decreased by {-d_avg:.2f} ms** (approx. latency per case)."
            )
    if d_wall is not None:
        lines.append(f"Wall-clock run duration delta: **{d_wall:+.0f} ms**.")

    return {
        "current": cur,
        "previous": prev,
        "delta_wall_ms": d_wall,
        "delta_metrics_duration_ms": d_metrics,
        "delta_avg_case_ms": d_avg,
        "summary_markdown": "\n\n".join(lines) if lines else None,
    }


def snapshot_files_for_download(*, record: RunRecord) -> list[tuple[str, Path]]:
    """Return ``(label, path)`` for files under the snapshot dir."""
    if not record.snapshot_dir:
        return []
    base = ORCHESTRATOR_ROOT / record.snapshot_dir
    if not base.is_dir():
        return []
    out: list[tuple[str, Path]] = []
    for p in sorted(base.rglob("*")):
        if p.is_file():
            rel = p.relative_to(base)
            out.append((str(rel), p))
    return out
