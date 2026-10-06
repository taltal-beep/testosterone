"""Report links and snapshot files for pre-v1.1 runs stored in MinIO / S3.

The removed headless runner uploaded each run's artifacts under
``runs/<run_id>/artifacts/`` and stored that prefix as the record's
``snapshot_dir``. Engine runs keep their artifacts on disk, so this module is
only reached for those older records. Every call is best-effort: when MinIO is
not configured or unreachable it returns nothing rather than failing the request.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_S3_PREFIX = "runs/"


def is_s3_snapshot(snapshot_dir: str | None) -> bool:
    """True when ``snapshot_dir`` is an object-store prefix rather than a local path."""
    return bool(snapshot_dir and snapshot_dir.startswith(_S3_PREFIX))


def _storage():  # noqa: ANN202 - returns ArtifactS3Storage or None
    try:
        from testo_core.s3_client import get_artifact_s3

        return get_artifact_s3()
    except Exception:
        logger.debug("S3 artifact storage unavailable", exc_info=True)
        return None


def report_links(snapshot_prefix: str) -> dict[str, str]:
    """Absolute MinIO URLs of the HTML reports under ``snapshot_prefix``, keyed by framework."""
    storage = _storage()
    if storage is None:
        return {}
    base = snapshot_prefix.rstrip("/")
    links: dict[str, str] = {}
    for fw in ("pytest", "behavex", "behave_native"):
        key = f"{base}/allure_reports/{fw}/index.html"
        if storage.object_exists(key):
            links[fw] = storage.public_url_for_key(key)
    if "pytest" not in links:
        for rel in ("allure_report/index.html", "allure_report.html"):
            key = f"{base}/{rel}"
            if storage.object_exists(key):
                links["pytest"] = storage.public_url_for_key(key)
                break
    behave_key = f"{base}/behave/index.html"
    if storage.object_exists(behave_key):
        links["behavex"] = storage.public_url_for_key(behave_key)
    return links


def snapshot_files(snapshot_prefix: str) -> list[tuple[str, bytes]]:
    """``(relative_path, bytes)`` for every object under ``snapshot_prefix``."""
    storage = _storage()
    if storage is None:
        return []
    prefix = snapshot_prefix.rstrip("/") + "/"
    out: list[tuple[str, bytes]] = []
    for key in sorted(storage.list_keys_under_prefix(prefix)):
        rel = key[len(prefix) :] if key.startswith(prefix) else ""
        if not rel:
            continue
        try:
            out.append((rel, storage.get_object_bytes(key)))
        except Exception:
            logger.debug("skipping unreadable snapshot object %s", key, exc_info=True)
    return out
