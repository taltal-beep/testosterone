from __future__ import annotations

import os

from fastapi import APIRouter, Response

from testo_api.models import HealthLiveResponse, HealthReadyResponse, ReadinessCheck
from testo_core.db import get_repository
from testo_core.db_config import get_engine
from testo_core.s3_client import get_artifact_s3

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("/live", response_model=HealthLiveResponse)
def live() -> HealthLiveResponse:
    return HealthLiveResponse(status="ok")


@router.get("/ready", response_model=HealthReadyResponse)
def ready(response: Response) -> HealthReadyResponse:
    checks: dict[str, ReadinessCheck] = {}

    try:
        engine = get_engine()
        with engine.connect():
            pass
        checks["db"] = ReadinessCheck(status="ok")
    except Exception as exc:  # pragma: no cover - dependency specific
        checks["db"] = ReadinessCheck(status="degraded", detail=str(exc))

    try:
        _ = get_repository()
        checks["repository"] = ReadinessCheck(status="ok")
    except Exception as exc:  # pragma: no cover - dependency specific
        checks["repository"] = ReadinessCheck(status="degraded", detail=str(exc))

    # MinIO only serves report snapshots of pre-v1.1 runs, so it is checked
    # only when it is configured; a fresh install without it is still ready.
    if _minio_configured():
        try:
            storage = get_artifact_s3()
            _ = storage.bucket_name
            checks["s3"] = ReadinessCheck(status="ok")
        except Exception as exc:  # pragma: no cover - dependency specific
            checks["s3"] = ReadinessCheck(status="degraded", detail=str(exc))

    is_degraded = any(check.status == "degraded" for check in checks.values())
    if is_degraded:
        response.status_code = 503
    return HealthReadyResponse(status="degraded" if is_degraded else "ready", checks=checks)


def _minio_configured() -> bool:
    return any(
        (os.getenv(name) or "").strip()
        for name in ("MINIO_ENDPOINT", "MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD")
    )
