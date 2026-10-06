"""Read model over persisted runs: list/get views, report links, snapshot downloads.

Runs are written by the engine's persistence backends
(:mod:`testo_core.persistence`); this module only reads them back for the API,
the dashboard and the AI failure analysis. Records written before v1.1 by the
removed headless runner (``test_kind`` per framework, MinIO snapshots) are still
readable here.
"""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ORCHESTRATOR_ROOT = Path(__file__).resolve().parents[1]
# When executed as a script (`python testo_core/run_history.py`), ensure imports like `testo_core.*` work.
if str(ORCHESTRATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_ROOT))

from testo_core.db import get_repository
from testo_core.db_config import (  # get_engine: back-compat re-export
    create_db_and_tables,
)
from testo_core.repository.models import RunRecord, RunStatus
from testo_core.s3_client import get_artifact_s3

logger = logging.getLogger(__name__)

STATIC_HISTORY_ROOT = ORCHESTRATOR_ROOT / "static" / "history"


def cleanup_orphaned_runs(*, note: str = "Orphaned due to system crash") -> int:
    """
    On startup, mark any RUNNING runs as FAILED.

    This prevents the UI from displaying runs that were interrupted by a crash or a force-quit
    (API server reload, kernel restart, machine reboot, etc.) as if they were still executing.
    """
    repo = get_repository()
    rows = repo.list_runs_by_status(RunStatus.RUNNING)
    if not rows:
        return 0
    now = _utcnow()
    to_persist: list[RunRecord] = []
    for r in rows:
        try:
            merged = dict(r.metadata_ or {})
            merged.setdefault("error", "orphaned")
            merged.setdefault("error_message", str(note))
            merged.setdefault("orphaned_at", float(time.time()))
            r.metadata_ = merged
            r.status = RunStatus.FAILED
            r.end_time = now
            to_persist.append(r)
        except Exception:
            continue
    updated = repo.bulk_update(to_persist)
    if updated:
        logger.warning("Marked %s orphaned RUNNING run(s) as FAILED (%s).", updated, note)
    return int(updated)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True)
class CompletedRunView:
    """
    Flat view of one run for the API and services.
    Derived from `RunRecord.metadata_`.
    """

    run_id: str
    status: RunStatus | None
    created_at: float
    started_at: float
    finished_at: float
    test_kind: str
    returncode: int
    wall_duration_ms: float
    metrics_duration_ms: int | None
    total_tests: int | None
    passed: int | None
    failed: int | None
    broken: int | None
    skipped: int | None
    avg_case_ms: float | None
    health_pct: float | None
    target_repo: str | None
    snapshot_dir: str | None
    audit_json: str | None
    cycle: str | None = None
    stage_health: list[dict[str, Any]] = field(default_factory=list)


def _is_s3_snapshot_prefix(snapshot_dir: str | None) -> bool:
    return bool(snapshot_dir and snapshot_dir.startswith("runs/"))


@dataclass(frozen=True)
class RunSessionView:
    """UI-friendly grouped run session with available report links."""

    run_id: str
    created_at: float
    returncode: int
    health_pct: float | None
    total_tests: int | None
    passed: int | None
    failed: int | None
    skipped: int | None
    broken: int | None
    status: RunStatus | None
    links_under_static: dict[str, str]
    cycle: str | None = None


def _s3_session_links(*, run_id: str, snap_prefix: str) -> dict[str, str]:
    """Build absolute MinIO URLs for reports under ``runs/<id>/artifacts/``."""
    links: dict[str, str] = {}
    try:
        storage = get_artifact_s3()
    except Exception:
        return links
    base = snap_prefix.rstrip("/")
    for fw in ("pytest", "behavex", "behave_native"):
        key = f"{base}/allure_reports/{fw}/index.html"
        if storage.object_exists(key):
            links[fw] = storage.public_url_for_key(key)
    if "pytest" not in links:
        for rel, _ in (
            ("allure_report/index.html", "pytest"),
            ("allure_report.html", "pytest"),
        ):
            key = f"{base}/{rel}"
            if storage.object_exists(key):
                links["pytest"] = storage.public_url_for_key(key)
                break
    behave_key = f"{base}/behave/index.html"
    if storage.object_exists(behave_key):
        links["behavex"] = storage.public_url_for_key(behave_key)
    return links


def list_run_sessions(*, limit: int = 30, db_path: Path | None = None) -> list[RunSessionView]:
    """
    Presentation-friendly run sessions grouped by the persisted ``run_id``.

    Prefers legacy paths under ``./static/history/<run_id>/`` when present; otherwise
    uses MinIO object URLs when ``snapshot_dir`` is an S3 prefix (``runs/.../artifacts``).
    """
    out: list[RunSessionView] = []
    for r in list_recent_runs(limit=limit, db_path=db_path):
        links: dict[str, str] = {}
        base = STATIC_HISTORY_ROOT / r.run_id
        # New layout: static/history/<run_id>/allure_reports/<framework>/index.html
        # Scanned dynamically (framework key = actual subdir name) rather than a
        # hardcoded taxonomy, since adapters name their subdirs after `equipment`
        # (e.g. "behave"), which doesn't match any fixed legacy key set.
        allure_reports_dir = base / "allure_reports"
        if allure_reports_dir.is_dir():
            for fw_dir in sorted(allure_reports_dir.iterdir()):
                if fw_dir.is_dir() and (fw_dir / "index.html").is_file():
                    links[fw_dir.name] = f"history/{r.run_id}/allure_reports/{fw_dir.name}/index.html"
        extent_index = base / "extent_report" / "index.html"
        if extent_index.is_file():
            links["extent"] = f"history/{r.run_id}/extent_report/index.html"
        # Each framework's own native report (e.g. BehaveX's own HTML dashboard),
        # distinct from the Allure-rendered view above — `-native` suffix avoids
        # colliding with the `allure_reports/<framework>` key of the same name.
        native_reports_dir = base / "native_reports"
        if native_reports_dir.is_dir():
            for fw_dir in sorted(native_reports_dir.iterdir()):
                if fw_dir.is_dir() and (fw_dir / "index.html").is_file():
                    links[f"{fw_dir.name}-native"] = f"history/{r.run_id}/native_reports/{fw_dir.name}/index.html"
        # Back-compat: older snapshots (single unified output) — map to pytest view for legacy history.
        if "pytest" not in links and (base / "allure_report" / "index.html").is_file():
            links["pytest"] = f"history/{r.run_id}/allure_report/index.html"
        if "pytest" not in links and (base / "allure_report.html").is_file():
            links["pytest"] = f"history/{r.run_id}/allure_report.html"
        if (base / "behave" / "index.html").is_file():
            links["behavex"] = f"history/{r.run_id}/behave/index.html"

        if not links and _is_s3_snapshot_prefix(r.snapshot_dir):
            links = _s3_session_links(run_id=r.run_id, snap_prefix=r.snapshot_dir or "")

        out.append(
            RunSessionView(
                run_id=r.run_id,
                created_at=r.created_at,
                returncode=r.returncode,
                cycle=r.cycle,
                health_pct=r.health_pct,
                total_tests=r.total_tests,
                passed=r.passed,
                failed=r.failed,
                skipped=r.skipped,
                broken=r.broken,
                status=r.status,
                links_under_static=links,
            )
        )
    return out


def allure_report_url_for_run(run_id: str) -> str:
    """Public URL for a pre-generated Allure 3 HTML bundle (nginx static host)."""
    import os

    base = (os.getenv("ALLURE_SERVER_URL") or "http://localhost:5050").rstrip("/")
    return f"{base}/reports/{run_id}/index.html"


def init_schema(db_path: Path | None = None) -> None:
    # Back-compat alias for older callers/tests.
    create_db_and_tables()


def _returncode_from_metadata(md: dict[str, Any]) -> int:
    """``DbBackend.persist`` (engine-sourced runs) writes ``exit_code``/``aggregate_returncode``
    but no plain ``returncode`` key; pre-v1.1 headless-runner records carry ``returncode`` directly.
    Prefer the explicit key, then fall back through the engine-shaped aliases.
    """
    for key in ("returncode", "aggregate_returncode", "exit_code"):
        value = md.get(key)
        if value is not None:
            return int(value)
    return 0


def _wall_duration_ms_from_metadata(md: dict[str, Any]) -> float:
    """``DbBackend.persist`` (engine-sourced runs) writes ``duration_s`` but no
    ``wall_duration_ms``; pre-v1.1 headless-runner records carry ``wall_duration_ms`` directly.
    """
    if md.get("wall_duration_ms") is not None:
        return float(md["wall_duration_ms"])
    if md.get("duration_s") is not None:
        return max(0.0, float(md["duration_s"]) * 1000.0)
    started, finished = md.get("started_at"), md.get("finished_at")
    if started is not None and finished is not None:
        return max(0.0, (float(finished) - float(started)) * 1000.0)
    return 0.0


def _health_pct_from_metadata(md: dict[str, Any]) -> float | None:
    if md.get("health_pct") is not None:
        return float(md["health_pct"])
    stages = md.get("stages")
    if isinstance(stages, list) and stages:
        passed_stages = sum(1 for s in stages if isinstance(s, dict) and s.get("returncode") == 0)
        return 100.0 * passed_stages / len(stages)
    return None


def _completed_view_from_record(r: RunRecord) -> CompletedRunView | None:
    md = r.metadata_ or {}
    run_id = md.get("run_id")
    if not run_id:
        return None
    return CompletedRunView(
        run_id=str(run_id),
        status=r.status if r.status is not None else None,
        created_at=float(md.get("created_at") or 0.0),
        started_at=float(md.get("started_at") or 0.0),
        finished_at=float(md.get("finished_at") or 0.0),
        test_kind=str(md.get("test_kind") or "unknown"),
        cycle=str(md["plan"]) if md.get("plan") else None,
        returncode=_returncode_from_metadata(md),
        wall_duration_ms=_wall_duration_ms_from_metadata(md),
        metrics_duration_ms=int(md["metrics_duration_ms"]) if md.get("metrics_duration_ms") is not None else None,
        total_tests=int(md["total_tests"]) if md.get("total_tests") is not None else None,
        passed=int(md["passed"]) if md.get("passed") is not None else None,
        failed=int(md["failed"]) if md.get("failed") is not None else None,
        broken=int(md["broken"]) if md.get("broken") is not None else None,
        skipped=int(md["skipped"]) if md.get("skipped") is not None else None,
        avg_case_ms=float(md["avg_case_ms"]) if md.get("avg_case_ms") is not None else None,
        health_pct=_health_pct_from_metadata(md),
        target_repo=str(md["target_repo"]) if md.get("target_repo") else None,
        snapshot_dir=str(md["snapshot_dir"]) if md.get("snapshot_dir") else None,
        audit_json=str(md["audit_json"]) if md.get("audit_json") else None,
        stage_health=[s for s in md.get("stages") or [] if isinstance(s, dict)],
    )


def list_recent_runs(*, limit: int = 30, db_path: Path | None = None) -> list[CompletedRunView]:
    del db_path  # Back-compat; repository uses ``DATABASE_URL`` / engine config.
    out: list[CompletedRunView] = []
    for r in get_repository().list_recent_runs(limit=limit):
        v = _completed_view_from_record(r)
        if v is not None:
            out.append(v)
    return out


def get_run(*, run_id: str, db_path: Path | None = None) -> CompletedRunView | None:
    del db_path  # Back-compat; repository uses ``DATABASE_URL`` / engine config.
    r = get_repository().get_run(run_id)
    if r is None:
        return None
    return _completed_view_from_record(r)


def get_run_metadata(*, run_id: str) -> dict[str, Any] | None:
    record = get_repository().get_run(run_id)
    if record is None:
        return None
    return dict(record.metadata_ or {})


def upsert_run_metadata(*, run_id: str, metadata_patch: dict[str, Any]) -> bool:
    record = get_repository().get_run(run_id)
    if record is None:
        return False
    merged = dict(record.metadata_ or {})
    merged.update(metadata_patch)
    record.metadata_ = merged
    get_repository().bulk_update([record])
    return True


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


def snapshot_files_for_download(*, record: CompletedRunView) -> list[tuple[str, bytes]]:
    """Return ``(relative_label, file_bytes)`` for captured snapshot artifacts."""
    if not record.snapshot_dir:
        return []
    if _is_s3_snapshot_prefix(record.snapshot_dir):
        try:
            storage = get_artifact_s3()
        except Exception:
            return []
        prefix = record.snapshot_dir.rstrip("/") + "/"
        out: list[tuple[str, bytes]] = []
        for key in sorted(storage.list_keys_under_prefix(prefix)):
            if not key.startswith(prefix):
                continue
            rel = key[len(prefix) :]
            if not rel:
                continue
            try:
                out.append((rel, storage.get_object_bytes(key)))
            except Exception:
                pass
        return out
    base = ORCHESTRATOR_ROOT / record.snapshot_dir
    if not base.is_dir():
        return []
    out: list[tuple[str, bytes]] = []
    for p in sorted(base.rglob("*")):
        if p.is_file():
            rel = p.relative_to(base)
            out.append((str(rel), p.read_bytes()))
    return out


if __name__ == "__main__":
    # Allow running as: `python testo_core/run_history.py`
    # Ensure project root is on sys.path so `import testo_core.*` resolves.
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    create_db_and_tables()
    print("Database connection and table creation successful!")
