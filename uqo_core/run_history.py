from __future__ import annotations

import json
import logging
import shutil
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Optional

ORCHESTRATOR_ROOT = Path(__file__).resolve().parents[1]
# When executed as a script (`python uqo_core/run_history.py`), ensure imports like `uqo_core.*` work.
if str(ORCHESTRATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_ROOT))

from uqo_core.db import get_repository
from uqo_core.db_config import create_db_and_tables, get_engine  # get_engine: back-compat re-export
from uqo_core.metrics import parse_allure_results_dir
from uqo_core.paths import (
    STATIC_ALLURE_HTML,
    STATIC_BEHAVE_DIR,
    STATIC_LOCUST_HTML,
)
from uqo_core.runners import RunResult
from uqo_core.repository.models import RunRecord, RunStatus
from uqo_core.s3_client import get_artifact_s3

logger = logging.getLogger(__name__)

STATIC_HISTORY_ROOT = ORCHESTRATOR_ROOT / "static" / "history"


def cleanup_orphaned_runs(*, note: str = "Orphaned due to system crash") -> int:
    """
    On startup, mark any RUNNING runs as FAILED.

    This prevents the UI from displaying runs that were interrupted by a crash or a force-quit
    (Streamlit reload, kernel restart, machine reboot, etc.) as if they were still executing.
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


def create_run(*, status: RunStatus = RunStatus.PENDING, metadata: Optional[dict[str, Any]] = None) -> uuid.UUID:
    """
    Initializes a new record in the DB.

    Returns the new run UUID.
    """
    rr = get_repository().create_run(status=status, metadata=metadata)
    return rr.id


def update_run_status(run_id: uuid.UUID | str, status: RunStatus, metadata: Optional[dict[str, Any]] = None) -> None:
    """
    Updates an existing record (or creates it if missing).
    """
    get_repository().update_run_status(run_id, status=status, metadata=metadata)


@dataclass(frozen=True)
class CompletedRunView:
    """
    Back-compat view for the Streamlit UI.
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


def _is_s3_snapshot_prefix(snapshot_dir: str | None) -> bool:
    return bool(snapshot_dir and snapshot_dir.startswith("runs/"))


def _snapshot_reports(*, run_id: str, artifacts_root: Path) -> str | None:
    """
    Stage report mirrors in a temp directory, upload to MinIO under
    ``runs/{run_id}/artifacts/...``, and return the key prefix ``runs/{run_id}/artifacts``.

    Does not write under ``artifacts/history/`` or ``static/history/``.
    """
    del artifacts_root  # Snapshot source is static mirrors, not the local artifacts tree.
    prefix = f"runs/{run_id}/artifacts"
    try:
        storage = get_artifact_s3()
    except Exception as exc:
        logger.warning("S3 artifact snapshot skipped (configure MinIO env): %s", exc)
        return None

    try:
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)
            dest.mkdir(parents=True, exist_ok=True)
            try:
                from .paths import STATIC_ALLURE_REPORTS_DIR

                allure_hist = dest / "allure_reports"
                allure_hist.mkdir(parents=True, exist_ok=True)
                if STATIC_ALLURE_REPORTS_DIR.is_dir():
                    for d in [p for p in STATIC_ALLURE_REPORTS_DIR.iterdir() if p.is_dir()]:
                        if d.name == "unified":
                            continue
                        if (d / "index.html").is_file():
                            shutil.copytree(d, allure_hist / d.name)
            except Exception:
                pass

            if not (dest / "allure_reports").is_dir() and STATIC_ALLURE_HTML.is_file():
                shutil.copy2(STATIC_ALLURE_HTML, dest / "allure_report.html")
            if STATIC_LOCUST_HTML.is_file():
                shutil.copy2(STATIC_LOCUST_HTML, dest / "locust_report.html")
            if STATIC_BEHAVE_DIR.is_dir() and any(STATIC_BEHAVE_DIR.iterdir()):
                shutil.copytree(STATIC_BEHAVE_DIR, dest / "behave")

            uploaded = 0
            for path in dest.rglob("*"):
                if path.is_file():
                    rel = path.relative_to(dest).as_posix()
                    key = f"{prefix}/{rel}"
                    storage.upload_file(path, key)
                    uploaded += 1
            if uploaded == 0:
                return None
            return prefix
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
    failed: int | None
    skipped: int | None
    broken: int | None
    status: RunStatus | None
    links_under_static: dict[str, str]


@dataclass(frozen=True)
class SyncOperationStatus:
    status: str
    attempts: int
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "attempts": int(self.attempts),
            "error": self.error,
        }


@dataclass(frozen=True)
class RunSyncStatus:
    run_id: str | None
    db_finalize: SyncOperationStatus
    artifact_upload: SyncOperationStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "db_finalize": self.db_finalize.to_dict(),
            "artifact_upload": self.artifact_upload.to_dict(),
        }


def _is_transient_sync_error(exc: Exception) -> bool:
    return isinstance(exc, (ConnectionError, TimeoutError, OSError))


def _run_with_retry(
    fn: Callable[[], None],
    *,
    max_attempts: int = 3,
    base_backoff_s: float = 0.1,
) -> tuple[int, Exception | None]:
    attempts = 0
    last_error: Exception | None = None
    while attempts < max_attempts:
        attempts += 1
        try:
            fn()
            return attempts, None
        except Exception as exc:  # pragma: no cover - exercised via callers
            last_error = exc
            if attempts >= max_attempts or not _is_transient_sync_error(exc):
                break
            time.sleep(base_backoff_s * float(2 ** (attempts - 1)))
    return attempts, last_error


def _s3_session_links(*, run_id: str, snap_prefix: str) -> dict[str, str]:
    """Build absolute MinIO URLs for reports under ``runs/<id>/artifacts/``."""
    links: dict[str, str] = {}
    try:
        storage = get_artifact_s3()
    except Exception:
        return links
    base = snap_prefix.rstrip("/")
    for fw in ("pytest", "behavex", "locust", "behave_native"):
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
    loc_key = f"{base}/locust_report.html"
    if storage.object_exists(loc_key):
        links["locust"] = storage.public_url_for_key(loc_key)
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
        for fw in ("pytest", "behavex", "locust", "behave_native"):
            p = base / "allure_reports" / fw / "index.html"
            if p.is_file():
                links[fw] = f"history/{r.run_id}/allure_reports/{fw}/index.html"
        # Back-compat: older snapshots (single unified output) — map to pytest view for legacy history.
        if "pytest" not in links and (base / "allure_report" / "index.html").is_file():
            links["pytest"] = f"history/{r.run_id}/allure_report/index.html"
        if "pytest" not in links and (base / "allure_report.html").is_file():
            links["pytest"] = f"history/{r.run_id}/allure_report.html"
        if (base / "locust_report.html").is_file():
            links["locust"] = f"history/{r.run_id}/locust_report.html"
        if (base / "behave" / "index.html").is_file():
            links["behavex"] = f"history/{r.run_id}/behave/index.html"

        if not links and _is_s3_snapshot_prefix(r.snapshot_dir):
            links = _s3_session_links(run_id=r.run_id, snap_prefix=r.snapshot_dir or "")

        out.append(
            RunSessionView(
                run_id=r.run_id,
                created_at=r.created_at,
                returncode=r.returncode,
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


def record_completed_run(
    *,
    rr: RunResult,
    artifacts_root: Path,
    test_kind: str,
    audit_health_pct: float | None = None,
    metadata_context: dict[str, Any] | None = None,
    db_path: Path | None = None,
) -> RunSyncStatus:
    """Persist metadata and snapshot HTML after a run completes."""
    del db_path
    env = rr.command.env
    run_id = env.get("UQO_AUDIT_RUN_ID") or env.get("UQO_RUN_ID")
    if not run_id:
        return RunSyncStatus(
            run_id=None,
            db_finalize=SyncOperationStatus(status="failed", attempts=0, error="missing_run_id"),
            artifact_upload=SyncOperationStatus(status="failed", attempts=0, error="missing_run_id"),
        )

    ar = artifacts_root.expanduser().resolve()
    results_dir = ar / "allure-results"
    scoped_results_dir: Path | None = None
    if not rr.audit_mode:
        scoped_results = env.get("UQO_SHARED_ALLURE_RESULTS_DIR")
        if scoped_results:
            results_dir = Path(scoped_results).expanduser().resolve()
            scoped_results_dir = results_dir
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

    snapshot_attempts = 0
    upload_attempts = 0
    artifact_error: str | None = None
    snap_prefix: str | None = None
    upload_count = 0
    snapshot_holder: dict[str, str | None] = {"prefix": None}
    upload_holder: dict[str, int] = {"count": 0}

    def _snapshot_op() -> None:
        snapshot_holder["prefix"] = _snapshot_reports(run_id=run_id, artifacts_root=ar)

    def _upload_op() -> None:
        upload_holder["count"] = _upload_allure_results_to_s3(
            run_id=str(run_id),
            artifacts_root=ar,
            test_kind=str(test_kind),
            scoped_results_dir=scoped_results_dir,
        )

    snapshot_attempts, snapshot_error = _run_with_retry(_snapshot_op)
    upload_attempts, upload_error = _run_with_retry(_upload_op)
    snap_prefix = snapshot_holder["prefix"]
    upload_count = int(upload_holder["count"])
    if snapshot_error is not None:
        artifact_error = str(snapshot_error)
    elif upload_error is not None:
        artifact_error = str(upload_error)

    target_repo = str(rr.command.cwd)
    payload: dict[str, Any] = {
        "run_id": str(run_id),
        "created_at": float(time.time()),
        "started_at": float(rr.started_at),
        "finished_at": float(rr.finished_at),
        "test_kind": str(test_kind),
        "returncode": int(rr.returncode),
        "wall_duration_ms": float(wall_ms),
        "metrics_duration_ms": int(metrics_ms) if metrics_ms is not None else None,
        "total_tests": int(total_t) if total_t is not None else None,
        "passed": int(passed) if passed is not None else None,
        "failed": int(failed) if failed is not None else None,
        "broken": int(getattr(m, "broken", 0)) if m is not None and getattr(m, "broken", None) is not None else None,
        "skipped": int(getattr(m, "skipped", 0)) if m is not None and getattr(m, "skipped", None) is not None else None,
        "avg_case_ms": float(avg_case) if avg_case is not None else None,
        "health_pct": float(health) if health is not None else None,
        "target_repo": str(target_repo),
        "snapshot_dir": snap_prefix,
        "audit_json": str(audit_blob) if audit_blob else None,
    }
    if metadata_context:
        payload.update({str(k): v for k, v in metadata_context.items()})
    if int(rr.returncode) == 124:
        payload.setdefault("error", "timeout")
        payload.setdefault("error_message", "Container exceeded timeout and was force-killed.")
    status = RunStatus.COMPLETED if int(rr.returncode) == 0 else RunStatus.FAILED
    db_attempts, db_error = _run_with_retry(lambda: update_run_status(run_id, status=status, metadata=payload))

    db_status = "success" if db_error is None else "failed"
    if artifact_error is not None:
        artifact_status = "failed"
    elif snap_prefix is None and upload_count <= 0:
        artifact_status = "skipped"
    else:
        artifact_status = "success"

    return RunSyncStatus(
        run_id=str(run_id),
        db_finalize=SyncOperationStatus(status=db_status, attempts=db_attempts, error=str(db_error) if db_error else None),
        artifact_upload=SyncOperationStatus(
            status=artifact_status,
            attempts=max(1, snapshot_attempts + upload_attempts),
            error=artifact_error,
        ),
    )


def _upload_allure_results_to_s3(
    *,
    run_id: str,
    artifacts_root: Path,
    test_kind: str,
    scoped_results_dir: Path | None = None,
) -> int:
    """
    Upload raw Allure results into MinIO for Allure Docker Service.

    We intentionally *flatten* the framework subfolders into a single project results folder
    for per-run Allure server reports.
    """
    try:
        storage = get_artifact_s3()
    except Exception as exc:
        logger.warning("Raw Allure results upload skipped (MinIO not configured): %s", exc)
        return 0

    ar = artifacts_root.expanduser().resolve()
    src_root = (ar / "allure-results").resolve()
    if not src_root.is_dir():
        return 0

    # Select which framework folders to include. Non-audit runs are isolated under
    # <framework>/<run_id>; use that scoped directory so a new S3 project never
    # inherits stale Allure payloads from prior runs in the same framework folder.
    include_dirs: list[Path] = []
    if str(test_kind).strip().lower() == "audit":
        for fw in ("pytest", "behavex", "behave_native"):
            p = (src_root / fw).resolve()
            if p.is_dir():
                include_dirs.append(p)
    else:
        p = scoped_results_dir.expanduser().resolve() if scoped_results_dir is not None else (src_root / str(test_kind)).resolve()
        if p.is_dir():
            include_dirs.append(p)

    if not include_dirs:
        return 0

    prefix = f"projects/{run_id}/results"

    uploaded = 0
    seen: set[str] = set()
    for base in include_dirs:
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            # Keep only valid Allure result payloads/attachments.
            # - JSON: result/container/categories/executors
            # - attachments: binary/text blobs referenced by tests
            if path.suffix.lower() not in {".json", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".xml", ".csv", ".log"}:
                # Still allow attachment files without suffix.
                if path.suffix:
                    continue
            name = path.name
            # Avoid overwriting same-named files across frameworks (best-effort).
            if name in seen:
                continue
            seen.add(name)
            key = f"{prefix}/{name}"
            storage.upload_file(path, key)
            uploaded += 1

    if uploaded:
        logger.info("Uploaded %s Allure result file(s) to s3://%s/%s", uploaded, storage.bucket_name, prefix)
    return int(uploaded)


def init_schema(db_path: Path | None = None) -> None:
    # Back-compat alias for older callers/tests.
    create_db_and_tables()


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
        returncode=int(md.get("returncode") or 0),
        wall_duration_ms=float(md.get("wall_duration_ms") or 0.0),
        metrics_duration_ms=int(md["metrics_duration_ms"]) if md.get("metrics_duration_ms") is not None else None,
        total_tests=int(md["total_tests"]) if md.get("total_tests") is not None else None,
        passed=int(md["passed"]) if md.get("passed") is not None else None,
        failed=int(md["failed"]) if md.get("failed") is not None else None,
        broken=int(md["broken"]) if md.get("broken") is not None else None,
        skipped=int(md["skipped"]) if md.get("skipped") is not None else None,
        avg_case_ms=float(md["avg_case_ms"]) if md.get("avg_case_ms") is not None else None,
        health_pct=float(md["health_pct"]) if md.get("health_pct") is not None else None,
        target_repo=str(md["target_repo"]) if md.get("target_repo") else None,
        snapshot_dir=str(md["snapshot_dir"]) if md.get("snapshot_dir") else None,
        audit_json=str(md["audit_json"]) if md.get("audit_json") else None,
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
    # Allow running as: `python uqo_core/run_history.py`
    # Ensure project root is on sys.path so `import uqo_core.*` resolves.
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    create_db_and_tables()
    print("Database connection and table creation successful!")
