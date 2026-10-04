from __future__ import annotations

from flask import Blueprint, render_template, request

from ..utils.responses import ok

bp = Blueprint("root", __name__)


@bp.get("/")
@bp.get("/api")
@bp.get("/api/")
@bp.get("/api/index")
@bp.get("/api/index.py")
@bp.get("/index.py")
def root():
    # If explicitly requested JSON or API client header without text/html
    accept = request.headers.get("Accept", "")
    if request.args.get("format") == "json" or ("application/json" in accept and "text/html" not in accept):
        return ok({
            "message": "Backend is running for WorkLog",
            "service": "WorkLog API",
            "status": "running",
        })

    try:
        return render_template("index.html")
    except Exception:
        return ok({
            "message": "Backend is running for WorkLog",
            "service": "WorkLog API",
            "status": "running",
        })
