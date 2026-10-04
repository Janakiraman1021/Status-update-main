from __future__ import annotations

from flask import Blueprint

from ..db import get_db
from ..utils.errors import ServiceUnavailable
from ..utils.responses import ok

bp = Blueprint("health", __name__, url_prefix="/api/health")


@bp.get("")
def health():
    try:
        get_db().command("ping")
    except Exception as exc:
        raise ServiceUnavailable("Database unavailable.", code="DB_UNAVAILABLE") from exc
    return ok({"status": "ok"})
