"""Raw artifact files captured for a run (``RunRecord.snapshot_dir``)."""

from __future__ import annotations

from testo_core import paths
from testo_core.history import s3_snapshots
from testo_core.history.views import CompletedRunView


def snapshot_files_for_download(*, record: CompletedRunView) -> list[tuple[str, bytes]]:
    """``(relative_path, bytes)`` for each file in the run's snapshot, sorted by path.

    Local ``snapshot_dir`` values are relative to the repository root; ``runs/…``
    prefixes are pre-v1.1 MinIO snapshots.
    """
    if not record.snapshot_dir:
        return []
    if s3_snapshots.is_s3_snapshot(record.snapshot_dir):
        return s3_snapshots.snapshot_files(record.snapshot_dir)
    base = paths.ORCHESTRATOR_ROOT / record.snapshot_dir
    if not base.is_dir():
        return []
    return [
        (str(p.relative_to(base)), p.read_bytes()) for p in sorted(base.rglob("*")) if p.is_file()
    ]
