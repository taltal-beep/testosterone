from __future__ import annotations

import logging

from fastapi import APIRouter, Response

from testo_api.models import HealthLiveResponse, HealthReadyResponse, ReadinessCheck
from testo_core.db import get_repository
from testo_core.db_config import get_engine

logger = logging.getLogger(__name__)

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
        # Broad on purpose: any failure is reported as "degraded" (503), never a crash.
        logger.debug("readiness: db check failed", exc_info=True)
        checks["db"] = ReadinessCheck(status="degraded", detail=str(exc))

    try:
        _ = get_repository()
        checks["repository"] = ReadinessCheck(status="ok")
    except Exception as exc:  # pragma: no cover - dependency specific
        # Broad on purpose: any failure is reported as "degraded" (503), never a crash.
        logger.debug("readiness: repository check failed", exc_info=True)
        checks["repository"] = ReadinessCheck(status="degraded", detail=str(exc))

    is_degraded = any(check.status == "degraded" for check in checks.values())
    if is_degraded:
        response.status_code = 503
    return HealthReadyResponse(status="degraded" if is_degraded else "ready", checks=checks)
