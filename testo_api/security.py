"""Minimal access control for a local developer tool.

The API starts test runs, i.e. it runs commands on the host by design. It binds
127.0.0.1 by default; these knobs keep that honest when it is not:

- ``TESTO_API_TOKEN``: when set, every mutating request needs
  ``Authorization: Bearer <token>`` or the session cookie that ``/login``
  hands out for that token. Reads stay open unless:
- ``TESTO_PROTECT_READS=1`` (with a token): every request needs the token or
  the cookie, including the UI, report files under ``/history`` and the live
  run stream, which a browser can't send a header with. Health checks and
  the login page stay open. See :func:`guard_read_request`.
- ``TESTO_CORS_ORIGINS``: comma-separated browser origins allowed to call the
  API. Defaults to the Vite dev and preview servers. A mutating request that
  carries any other ``Origin`` is refused even without a token, because CORS
  alone does not stop a "simple" cross-site POST (or a DNS-rebinding page)
  from reaching a localhost server. With a token set, the UI served by this
  process (same origin, see :mod:`testo_api.ui`) may write too; the token
  still has to be sent.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from fastapi import HTTPException, Request
from starlette.responses import JSONResponse, RedirectResponse, Response

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# File names config discovery accepts (``config/loader.py``); see ``read_config_path``.
CONFIG_FILE_NAMES = frozenset({"testosterone.yaml", "testosterone.yml", "pyproject.toml"})
SESSION_COOKIE = "testo_session"
LOGIN_PATH = "/login"
LOGIN_POST_PATH = "/api/v1/auth/login"
# Reachable without a session even when reads are protected.
_OPEN_PATHS = frozenset({LOGIN_PATH, LOGIN_POST_PATH, "/api/v1/auth/logout"})
_OPEN_PREFIXES = ("/api/v1/health/",)


def api_token() -> str:
    return os.getenv("TESTO_API_TOKEN", "").strip()


def reads_protected() -> bool:
    """``TESTO_PROTECT_READS`` is on and there is a token to protect them with."""
    flag = os.getenv("TESTO_PROTECT_READS", "0").strip().lower() in ("1", "true", "yes")
    return flag and bool(api_token())


def session_value(token: str) -> str:
    """The cookie value for ``token``: derived from it, so the cookie never holds
    the token itself, and changing the token signs everyone out."""
    return hmac.new(token.encode(), b"testo-session-v1", hashlib.sha256).hexdigest()


def is_authenticated(request: Request) -> bool:
    """A valid bearer token or session cookie (always False without a token)."""
    expected = api_token()
    if not expected:
        return False
    scheme, _, supplied = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() == "bearer" and hmac.compare_digest(
        supplied.strip().encode(), expected.encode()
    ):
        return True
    cookie = request.cookies.get(SESSION_COOKIE, "")
    return bool(cookie) and hmac.compare_digest(cookie.encode(), session_value(expected).encode())


def safe_next(raw: str | None) -> str:
    """Where to go after login: a path on this server only, never another host."""
    if not raw or not raw.startswith("/") or raw.startswith(("//", "/\\")):
        return "/"
    return raw


def cors_settings() -> tuple[list[str], bool]:
    """Return ``(allowed_origins, allow_credentials)`` for ``CORSMiddleware``.

    Credentials are only allowed for an explicit origin list: browsers reject
    them with ``*``. The UI that uses the session cookie is served by the API
    itself (same origin), so it needs no CORS credentials either.
    """
    raw = os.getenv("TESTO_CORS_ORIGINS", "")
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if not origins:
        return list(DEFAULT_CORS_ORIGINS), False
    return origins, "*" not in origins


def guard_mutating_request(request: Request) -> None:
    """App-wide dependency: refuse foreign-origin writes and enforce ``TESTO_API_TOKEN``."""
    if request.method in _SAFE_METHODS:
        return
    origin = request.headers.get("Origin")
    allowed_origins, _ = cors_settings()
    expected = api_token()
    if (
        origin is not None
        and "*" not in allowed_origins
        and origin not in allowed_origins
        and not (expected and _is_same_origin(request, origin))
    ):
        raise HTTPException(
            status_code=403,
            detail=f"Origin {origin!r} is not allowed (set TESTO_CORS_ORIGINS).",
        )
    # The login form is how a browser gets a session, so it can't need one.
    if not expected or request.url.path == LOGIN_POST_PATH:
        return
    if not is_authenticated(request):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def guard_read_request(request: Request) -> Response | None:
    """With ``TESTO_PROTECT_READS``: the response that turns away a request
    without a session, or None to let it through.

    Runs as middleware rather than a route dependency so it also covers the
    ``/history`` report files and the UI, which are static mounts. A browser
    asking for a page is sent to ``/login``; anything else gets the API's 401.
    """
    if not reads_protected() or request.method == "OPTIONS":
        return None
    path = request.url.path
    if path in _OPEN_PATHS or path.startswith(_OPEN_PREFIXES) or is_authenticated(request):
        return None
    wants_page = request.method in ("GET", "HEAD") and "text/html" in request.headers.get(
        "Accept", ""
    )
    if wants_page and not path.startswith("/api/"):
        target = path + (f"?{request.url.query}" if request.url.query else "")
        return RedirectResponse(f"{LOGIN_PATH}?{urlencode({'next': target})}", status_code=303)
    return JSONResponse(
        status_code=401,
        content={
            "error": {
                "code": "unauthorized",
                "message": f"Sign in at {LOGIN_PATH} or send the API token.",
                "details": None,
            },
            "request_id": getattr(request.state, "request_id", None),
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


_ATTACHMENT_MARKERS = ("-attachment", "/data/attachments/")


def add_security_headers(request: Request, response: Response) -> None:
    """Headers every response gets, plus a sandbox for report attachments.

    Report files under ``/history`` share the API's origin, so an uploaded HTML
    attachment would otherwise run script with the viewer's session. Allure names
    attachments ``<uuid>-attachment.<ext>`` in results and copies them to
    ``data/attachments/`` in a report; those get ``sandbox``, which blocks script
    while still letting the report show the file. The report pages themselves keep
    working, since they need script and their own origin to load their data.
    """
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    path = request.url.path
    if path.startswith("/history/") and any(m in path for m in _ATTACHMENT_MARKERS):
        response.headers["Content-Security-Policy"] = "sandbox; frame-ancestors 'self'"
    else:
        response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'self'")


def read_config_path(raw: str | None) -> Path | None:
    """``?config_path=`` on a read route, limited to config file names.

    Reads need no token, so an arbitrary path would let anyone who can reach the
    API probe for files and see fragments of them in parse errors. Only a file
    named like a config (``testosterone.yaml``, ``testosterone.yml``,
    ``pyproject.toml``) is loaded; writes, which need the token, take any path.
    """
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    if path.name not in CONFIG_FILE_NAMES:
        raise HTTPException(
            status_code=400,
            detail="config_path must name a testosterone.yaml, testosterone.yml or pyproject.toml file.",
        )
    return path


def _is_same_origin(request: Request, origin: str) -> bool:
    """The UI served by this process (``TESTO_UI_DIR``) posting back to it.

    Only trusted together with a token: a DNS-rebinding page is "same origin"
    too, so without ``TESTO_API_TOKEN`` the Origin allow-list stays the only guard.
    """
    host = request.headers.get("Host", "")
    return bool(host) and urlsplit(origin).netloc.lower() == host.lower()


def is_loopback_host(host: str) -> bool:
    host = host.strip("[]").rstrip(".")
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
