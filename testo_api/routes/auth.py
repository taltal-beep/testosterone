"""Browser sign-in for a team server: trade the API token for a session cookie.

Report links open in a new tab and the live run stream uses ``EventSource``;
neither can send an ``Authorization`` header, so a browser proves itself with
an HttpOnly cookie instead (see :mod:`testo_api.security`). The page is plain
HTML from the API so it works before, and without, the React UI.
"""

from __future__ import annotations

import hmac
from html import escape

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from testo_api.security import (
    LOGIN_PATH,
    LOGIN_POST_PATH,
    SESSION_COOKIE,
    api_token,
    safe_next,
    session_value,
)

router = APIRouter(tags=["auth"])

SESSION_MAX_AGE = 30 * 24 * 3600

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in · Testosterone</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #0f1115; color: #e6e8eb;
         display: grid; place-items: center; min-height: 100vh; margin: 0; }}
  form {{ background: #181b21; padding: 2rem; border-radius: 12px; width: min(22rem, 90vw); }}
  h1 {{ font-size: 1.2rem; margin: 0 0 1rem; }}
  label {{ display: block; font-size: .85rem; margin-bottom: .4rem; color: #a3a9b3; }}
  input {{ width: 100%; box-sizing: border-box; padding: .6rem; border-radius: 8px;
          border: 1px solid #333944; background: #0f1115; color: inherit; }}
  button {{ margin-top: 1rem; width: 100%; padding: .6rem; border: 0; border-radius: 8px;
           background: #e2553f; color: white; font-weight: 600; cursor: pointer; }}
  p.error {{ color: #ff8a7a; font-size: .85rem; }}
</style>
</head>
<body>
<form method="post" action="{action}">
  <h1>Sign in to Testosterone</h1>
  {error}
  <label for="token">Team server token (<code>TESTO_API_TOKEN</code>)</label>
  <input id="token" name="token" type="password" autocomplete="current-password" required autofocus>
  <input type="hidden" name="next" value="{next}">
  <button type="submit">Sign in</button>
</form>
</body>
</html>
"""


def _page(next_path: str, error: str = "", status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        _PAGE.format(
            action=LOGIN_POST_PATH,
            next=escape(next_path, quote=True),
            error=f'<p class="error">{escape(error)}</p>' if error else "",
        ),
        status_code=status_code,
    )


@router.get(LOGIN_PATH, include_in_schema=False)
def login_page(next: str | None = None) -> HTMLResponse:  # noqa: A002 - query name
    return _page(safe_next(next))


@router.post(LOGIN_POST_PATH, include_in_schema=False)
def login(
    request: Request,
    token: str = Form(...),
    next: str = Form("/"),  # noqa: A002 - form field name
) -> Response:
    expected = api_token()
    target = safe_next(next)
    if not expected:
        return _page(
            target, "This server has no TESTO_API_TOKEN, so there is nothing to sign in to.", 400
        )
    if not hmac.compare_digest(token.strip().encode(), expected.encode()):
        return _page(target, "That token is not right.", 401)
    response = RedirectResponse(target, status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        session_value(expected),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="strict",
        # Behind an HTTPS proxy, set FORWARDED_ALLOW_IPS to the proxy's address so
        # uvicorn trusts its X-Forwarded-Proto and this sees "https".
        secure=request.url.scheme == "https",
        path="/",
    )
    return response


@router.post("/api/v1/auth/logout", include_in_schema=False)
def logout() -> Response:
    response = RedirectResponse(LOGIN_PATH, status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response
