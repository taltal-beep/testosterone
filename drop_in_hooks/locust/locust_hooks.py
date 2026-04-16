from __future__ import annotations

import io
import os
import statistics
import time
import traceback
import uuid
from collections import deque
from pathlib import Path
from typing import Deque, Dict

from locust import events

from allure_commons.logger import AllureFileLogger
from allure_commons.model2 import Attachment, Label, Parameter, Status, StatusDetails, TestResult


def _results_dir() -> Path | None:
    raw = os.environ.get("UQO_SHARED_ALLURE_RESULTS_DIR", "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


_LOGGERS: Dict[str, AllureFileLogger] = {}


def _logger_for(results_dir: Path) -> AllureFileLogger:
    key = str(results_dir)
    logger = _LOGGERS.get(key)
    if logger is None:
        logger = AllureFileLogger(report_dir=key, clean=False)
        _LOGGERS[key] = logger
    return logger


def _maybe_trend_png(latencies_ms: Deque[float], title: str) -> tuple[bytes | None, str]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: WPS433
    except Exception as exc:  # pragma: no cover
        return None, f"matplotlib unavailable: {exc}"

    if len(latencies_ms) < 2:
        return None, "not enough points"

    fig, ax = plt.subplots(figsize=(6, 2.2), dpi=120)
    ax.plot(list(latencies_ms), marker="o", linewidth=1)
    ax.set_title(title)
    ax.set_xlabel("last N requests")
    ax.set_ylabel("latency (ms)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue(), "ok"


@events.request.add_listener
def _uqo_on_request(request_type, name, response_time, response_length, exception=None, **_kwargs):
    results_dir = _results_dir()
    if results_dir is None:
        return

    now_ms = int(time.time() * 1000)
    latency_ms = float(response_time or 0.0)

    # Rolling window for simple spike detection.
    if not hasattr(_uqo_on_request, "_latencies"):
        setattr(_uqo_on_request, "_latencies", deque(maxlen=50))  # type: ignore[attr-defined]

    latencies: Deque[float] = getattr(_uqo_on_request, "_latencies")  # type: ignore[assignment]
    latencies.append(latency_ms)

    spike = False
    if len(latencies) >= 5:
        baseline = list(latencies)[-5:-1]
        if baseline:
            med = float(statistics.median(baseline))
            if med > 0 and latency_ms >= max(1000.0, med * 3.0):
                spike = True

    failed = exception is not None
    should_plot = failed or spike

    attachments: list[Attachment] = []

    overview = (
        f"request_type={request_type}\n"
        f"name={name}\n"
        f"response_time_ms={latency_ms}\n"
        f"response_length={response_length}\n"
        f"exception={repr(exception) if exception else ''}\n"
    )
    attachments.append(
        Attachment(
            name="locust.request.overview",
            source=_write_tmp_text(results_dir, overview),
            type="text/plain",
        )
    )

    if exception:
        tb = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        attachments.append(
            Attachment(
                name="locust.request.exception",
                source=_write_tmp_text(results_dir, tb),
                type="text/plain",
            )
        )

    if should_plot:
        png, _reason = _maybe_trend_png(latencies, title=f"{request_type} {name}")
        if png:
            png_path = results_dir / f"uqo_locust_trend_{uuid.uuid4().hex}.png"
            png_path.write_bytes(png)
            attachments.append(
                Attachment(
                    name="locust.latency.trend",
                    source=str(png_path.resolve()),
                    type="image/png",
                )
            )

    test_uuid = str(uuid.uuid4())
    status = Status.FAILED if failed else Status.PASSED
    status_details = None
    if failed:
        status_details = StatusDetails(
            message=str(exception),
            trace="".join(traceback.format_exception(type(exception), exception, exception.__traceback__)),
        )

    labels = [
        Label(name="framework", value="locust"),
        Label(name="suite", value="uqo-locust-requests"),
        Label(name="testType", value="request"),
    ]
    if os.environ.get("UQO_RUN_ID"):
        labels.append(Label(name="UQO_RUN_ID", value=os.environ["UQO_RUN_ID"]))

    parameters = [
        Parameter(name="request_type", value=str(request_type)),
        Parameter(name="name", value=str(name)),
        Parameter(name="response_time_ms", value=str(latency_ms)),
        Parameter(name="response_length", value=str(response_length)),
    ]

    result = TestResult(
        uuid=test_uuid,
        name=f"{request_type} {name}",
        fullName=f"locust.requests::{request_type}::{name}",
        status=status,
        statusDetails=status_details,
        start=now_ms,
        stop=now_ms,
        labels=labels,
        parameters=parameters,
        attachments=attachments,
    )

    _logger_for(results_dir).report_result(result)


def _write_tmp_text(results_dir: Path, text: str) -> str:
    p = results_dir / f"uqo_locust_attach_{uuid.uuid4().hex}.txt"
    p.write_text(text, encoding="utf-8")
    return str(p.resolve())
