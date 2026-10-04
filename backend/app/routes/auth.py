from __future__ import annotations

from flask import Blueprint, current_app, g, request

from ..middleware.auth import client_ip, login_required, session_token
from ..services import get_services
from ..services.auth_service import public_user
from ..utils.responses import ok
from ..utils.validators import LoginRequest, parse_body

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _settings_snapshot(user_id) -> dict:
    s = get_services().settings.get(user_id)
    return {"theme": s["theme"], "timezone": s["timezone"]}


@bp.post("/login")
def login():
    body = parse_body(LoginRequest)
    result = get_services().auth.login(body.email, body.password, body.remember, client_ip(), request.headers.get("User-Agent"))
    config = current_app.config["SETTINGS"]
    response, status = ok({
        "user": public_user(result.user),
        "csrf_token": result.csrf_token,
        "expires_at": result.expires_at,
        "settings": _settings_snapshot(result.user["_id"]),
    })
    response.set_cookie(
        config.SESSION_COOKIE_NAME, result.token,
        # Browser-session cookie unless "remember me"; the server-side session expiry applies either way.
        max_age=config.REMEMBER_TTL_DAYS * 86400 if result.remember else None,
        httponly=True, secure=config.cookie_secure, samesite="Lax", path="/",
    )
    return response, status


@bp.post("/logout")
def logout():
    get_services().auth.logout(session_token())
    config = current_app.config["SETTINGS"]
    response, status = ok({"logged_out": True})
    response.delete_cookie(config.SESSION_COOKIE_NAME, path="/", httponly=True, secure=config.cookie_secure, samesite="Lax")
    return response, status


@bp.get("/me")
@login_required
def me():
    return ok({"user": public_user(g.user), "csrf_token": g.session["csrf_token"], "expires_at": g.session["expires_at"],
               "settings": _settings_snapshot(g.user["_id"])})
