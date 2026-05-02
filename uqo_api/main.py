from __future__ import annotations

import os
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from uqo_api.routes.events import router as events_router
from uqo_api.routes.health import router as health_router
from uqo_api.routes.history import router as history_router
from uqo_api.routes.runs import router as runs_router


def create_app() -> FastAPI:
    app = FastAPI(title="UQO API", version="1.0.0")

    allowed_origins = [origin.strip() for origin in os.getenv("UQO_API_CORS_ORIGINS", "*").split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(runs_router)
    app.include_router(events_router)
    app.include_router(history_router)
    app.include_router(health_router)

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
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": str(exc.detail),
                    "details": None,
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
