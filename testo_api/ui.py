"""Serve the built React UI from the API process (``testo ui`` and the team server image).

The UI is a ``npm run build`` output built with ``VITE_API_BASE_URL=""`` so it
calls the API on its own origin. Released wheels carry one in
``testo_api/ui_dist/`` (the publish workflow builds it, see
``scripts/build_ui_bundle.sh``); ``TESTO_UI_DIR`` points at another build and
wins over the bundled one. The UI is mounted at ``/``, after every API route,
and unknown paths fall back to ``index.html`` so client-side routes like
``/runs/<id>`` load on refresh.
"""

from __future__ import annotations

import os
from pathlib import Path

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

UI_DIR_ENV = "TESTO_UI_DIR"
# Where a released wheel carries the built UI (empty in a source checkout).
BUNDLED_UI_DIR = Path(__file__).resolve().parent / "ui_dist"


def ui_dir() -> Path | None:
    """The UI build to serve: ``TESTO_UI_DIR`` if set, else the bundled one, else None."""
    raw = (os.environ.get(UI_DIR_ENV) or "").strip()
    path = Path(raw).expanduser().resolve() if raw else BUNDLED_UI_DIR
    return path if (path / "index.html").is_file() else None


class SpaStaticFiles(StaticFiles):
    """Static files with a single-page-app fallback to ``index.html``."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            # API and report paths keep their real 404; only UI routes fall back.
            if exc.status_code != 404 or path.startswith(("api/", "history/")):
                raise
            return await super().get_response("index.html", scope)
