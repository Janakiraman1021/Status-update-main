"""Authentication and CSRF enforcement for protected endpoints.

The session token travels only in an HttpOnly cookie. Mutating requests must also carry the
per-session CSRF token in the X-CSRF-Token header (synchronizer-token pattern) and use a JSON body.
"""
from __future__ import annotations

from functools import wraps

from flask import current_app, g, request

from ..services import get_services
from ..utils.errors import Forbidden, Unauthorized
from ..utils.security import constant_time_equals

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_HEADER = "X-CSRF-Token"


def session_token() -> str | None:
    return request.cookies.get(current_app.config["SETTINGS"].SESSION_COOKIE_NAME)


def client_ip() -> str:
    if current_app.config["SETTINGS"].TRUST_PROXY:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        resolved = get_services().auth.resolve_session(session_token())
        if not resolved:
            raise Unauthorized()
        g.user, g.session = resolved
        if request.method not in SAFE_METHODS:
            if not constant_time_equals(request.headers.get(CSRF_HEADER), g.session.get("csrf_token")):
                raise Forbidden("Your session security token is missing or invalid. Please reload the page.", code="CSRF_FAILED")
        return view(*args, **kwargs)

    return wrapper


def current_user() -> dict:
    return g.user


def current_user_id():
    return g.user["_id"]
