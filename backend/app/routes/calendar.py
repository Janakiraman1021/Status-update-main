from __future__ import annotations

from flask import Blueprint, request

from ..middleware.auth import current_user_id, login_required
from ..services import get_services
from ..utils.datetime_utils import local_now
from ..utils.errors import ValidationFailed
from ..utils.responses import ok

bp = Blueprint("calendar", __name__, url_prefix="/api/calendar")


@bp.get("")
@login_required
def month():
    services = get_services()
    now = local_now(services.settings.timezone(current_user_id()))
    try:
        year = int(request.args.get("year", now.year))
        month_number = int(request.args.get("month", now.month))
    except ValueError as exc:
        raise ValidationFailed("year and month must be integers.") from exc
    return ok(services.dashboard.calendar(current_user_id(), year, month_number))
