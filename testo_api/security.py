"""Minimal access control for a local developer tool.

The API starts test runs, i.e. it runs commands on the host by design. It binds
127.0.0.1 by default; these knobs keep that honest when it is not:

- ``TESTO_API_TOKEN``: when set, every mutating request needs
  ``Authorization: Bearer <token>``. Reads stay open.
- ``TESTO_CORS_ORIGINS``: comma-separated browser origins allowed to call the
  API. Defaults to the Vite dev and preview servers. A mutating request that
  carries any other ``Origin`` is refused even without a token, because CORS
  alone does not stop a "simple" cross-site POST (or a DNS-rebinding page)
  from reaching a localhost server. With a token set, the UI served by this
  process (same origin, see :mod:`testo_api.ui`) may write too; the token
  still has to be sent.
"""

from __future__ import annotations

import hmac
import ipaddress
import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# File names config discovery accepts (``config/loader.py``); see ``read_config_path``.
CONFIG_FILE_NAMES = frozenset({"testosterone.yaml", "testosterone.yml", "pyproject.toml"})


def cors_settings() -> tuple[list[str], bool]:
    """Return ``(allowed_origins, allow_credentials)`` for ``CORSMiddleware``.

    Credentials are only allowed for an explicit origin list: browsers reject
    them with ``*``, and the bundled frontend uses a bearer header, not cookies.
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
    expected = os.getenv("TESTO_API_TOKEN", "").strip()
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
    if not expected:
        return
    scheme, _, supplied = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(
        supplied.strip().encode(), expected.encode()
    ):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


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
