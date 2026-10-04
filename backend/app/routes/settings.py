from __future__ import annotations

from flask import Blueprint, current_app

from ..middleware.auth import current_user, login_required
from ..services import get_services
from ..services.auth_service import public_user
from ..utils.datetime_utils import list_timezones
from ..utils.responses import ok
from ..utils.validators import SettingsUpdate, dump, parse_body

bp = Blueprint("settings", __name__, url_prefix="/api/settings")


def _payload(user: dict) -> dict:
    services = get_services()
    config = current_app.config["SETTINGS"]
    return {
        "profile": public_user(user),
        "preferences": services.settings.get(user["_id"]),
        "email": services.email.status(),
        "ai": {"provider": services.ai.name, "model": services.ai.model},
        "scheduler": {"enabled": config.SCHEDULER_ENABLED, "interval_seconds": config.SCHEDULER_INTERVAL_SECONDS},
    }


@bp.get("")
@login_required
def get_settings():
    return ok(_payload(current_user()))


@bp.put("")
@login_required
def update_settings():
    data = dump(parse_body(SettingsUpdate))
    get_services().settings.update(current_user(), data)
    return ok(_payload(current_user()))


@bp.get("/timezones")
@login_required
def timezones():
    return ok(list_timezones())
