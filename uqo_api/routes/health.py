from __future__ import annotations

from fastapi import APIRouter, Response

from uqo_api.models import HealthLiveResponse, HealthReadyResponse, ReadinessCheck
from uqo_core.db import get_repository
from uqo_core.db_config import get_engine
from uqo_core.s3_client import get_artifact_s3

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
