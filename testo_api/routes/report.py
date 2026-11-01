"""The manager report: ``GET /api/v1/report`` (the UI's ``/report`` page reads it)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from testo_api.models import ManagerReportResponse
from testo_core.services.manager_report import build_report

router = APIRouter(prefix="/api/v1", tags=["report"])

Period = Literal["day", "week", "month", "quarter"]


@router.get("/report", response_model=ManagerReportResponse)
def get_report(
    period: Period = "week",
    cycle: list[str] | None = Query(
        None, description="Cycles to include; repeat. All when left out."
    ),
    title: str | None = Query(None, max_length=120),
) -> ManagerReportResponse:
    """How testing went over the last ``period``, against the period before, for every cycle or ``cycle``."""
    report = build_report(period=period, cycles=cycle, title=title or None)
    return ManagerReportResponse.model_validate(report.to_dict())
