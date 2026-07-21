from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from testo_core.run_history import STATIC_HISTORY_ROOT

from testo_api.routes.ai import router as ai_router
from testo_api.routes.analytics import router as analytics_router
from testo_api.routes.dashboard import router as dashboard_router
from testo_api.routes.cycles import router as cycles_router
from testo_api.routes.events import router as events_router
from testo_api.routes.health import router as health_router
from testo_api.routes.history import router as history_router
from testo_api.routes.runs import router as runs_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Runs left "RUNNING" by a crashed/reloaded process would otherwise sit
    # stuck forever in the UI history; mark them FAILED so the run list stays honest.
    from testo_core.run_history import cleanup_orphaned_runs

    try:
        n = cleanup_orphaned_runs(note="Orphaned by API server restart")
        if n:
            logger.warning("Cleaned up %s orphaned RUNNING run(s) on startup.", n)
    except Exception:
        logger.debug("orphaned-run cleanup skipped (DB unavailable?)", exc_info=True)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="UQO API", version="1.0.0", lifespan=_lifespan)

    allowed_origins = [origin.strip() for origin in os.getenv("UQO_API_CORS_ORIGINS", "*").split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(runs_router)
    app.include_router(ai_router)
    app.include_router(events_router)
    app.include_router(cycles_router)
    app.include_router(history_router)
    app.include_router(analytics_router)
    app.include_router(dashboard_router)
    app.include_router(health_router)

    STATIC_HISTORY_ROOT.mkdir(parents=True, exist_ok=True)
    app.mount("/history", StaticFiles(directory=STATIC_HISTORY_ROOT), name="history")

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):  # type: ignore[no-redef]
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:  # type: ignore[no-redef]
        status_map = {
            400: "invalid_input",
            404: "not_found",
            409: "domain_failure",
            422: "invalid_input",
            503: "infra_failure",
        }
        code = status_map.get(exc.status_code, "internal_error")
        message = str(exc.detail)
        details = None
        if isinstance(exc.detail, dict):
            maybe_code = exc.detail.get("code")
            if isinstance(maybe_code, str):
                code = maybe_code
            maybe_message = exc.detail.get("message")
            if isinstance(maybe_message, str):
                message = maybe_message
            maybe_details = exc.detail.get("details")
            if isinstance(maybe_details, dict):
                details = maybe_details
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "details": details,
                },
                "request_id": getattr(request.state, "request_id", str(uuid4())),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:  # type: ignore[no-redef]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_input",
                    "message": "Request validation failed.",
                    "details": {"errors": exc.errors()},
                },
                "request_id": getattr(request.state, "request_id", str(uuid4())),
            },
        )
    return app


app = create_app()


def run(argv: list[str] | None = None) -> int:
    """Console-script entry-point for ``testo-api``.

    Launches the FastAPI app with ``uvicorn``. Both packages are optional
    extras; if ``uvicorn`` is missing, a friendly message is printed instead
    of an opaque ``ModuleNotFoundError``.
    """
    import os
    import sys

    try:
        import uvicorn  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        sys.stderr.write(
            "uvicorn is not installed. Run `pip install testo-core[api]` first.\n"
        )
        return 1

    host = os.environ.get("TESTO_API_HOST", "127.0.0.1")
    port = int(os.environ.get("TESTO_API_PORT", "8000"))
    reload = os.environ.get("TESTO_API_RELOAD", "0") in ("1", "true", "True")
    uvicorn.run("testo_api.main:app", host=host, port=port, reload=reload)
    return 0

