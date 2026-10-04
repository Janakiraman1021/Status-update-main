from __future__ import annotations

from flask import Blueprint

from ..middleware.auth import current_user, login_required
from ..services import get_services
from ..utils.responses import ok

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@bp.get("")
@login_required
def dashboard():
    return ok(get_services().dashboard.dashboard(current_user()))
