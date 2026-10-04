from __future__ import annotations

from flask import Blueprint

from ..middleware.auth import current_user_id, login_required
from ..services import get_services
from ..utils.responses import ok
from ..utils.validators import WorkLogUpdate, WorkLogUpsert, dump, object_id, parse_body

bp = Blueprint("work_logs", __name__, url_prefix="/api/work-logs")


@bp.get("/<work_date>")
@login_required
def get_day(work_date: str):
    return ok(get_services().work_logs.day(current_user_id(), work_date))


@bp.post("")
@login_required
def upsert():
    data = dump(parse_body(WorkLogUpsert))
    work_date = data.pop("work_date")
    return ok(get_services().work_logs.upsert(current_user_id(), work_date, data))


@bp.put("/<log_id>")
@login_required
def update(log_id: str):
    data = dump(parse_body(WorkLogUpdate))
    return ok(get_services().work_logs.update(current_user_id(), object_id(log_id, "work log"), data))


@bp.delete("/<log_id>")
@login_required
def delete(log_id: str):
    get_services().work_logs.delete(current_user_id(), object_id(log_id, "work log"))
    return ok({"deleted": True})
