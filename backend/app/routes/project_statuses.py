from __future__ import annotations

from flask import Blueprint, request

from ..middleware.auth import current_user_id, login_required
from ..services import get_services
from ..utils.responses import ok
from ..utils.validators import ProjectStatusUpsert, dump, object_id, parse_body

bp = Blueprint("project_statuses", __name__, url_prefix="/api/project-statuses")


@bp.get("")
@login_required
def list_or_get():
    project_id = object_id(request.args.get("project_id", ""), "project")
    work_date = request.args.get("work_date")
    service = get_services().project_statuses
    if work_date:
        return ok(service.get(current_user_id(), project_id, work_date))
    return ok(service.list(current_user_id(), project_id))


@bp.post("")
@login_required
def upsert():
    body = dump(parse_body(ProjectStatusUpsert))
    return ok(get_services().project_statuses.save(current_user_id(), body))
