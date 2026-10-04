from __future__ import annotations

from flask import Blueprint, request

from ..constants import BLOCKER_STATUSES
from ..middleware.auth import current_user_id, login_required
from ..services import get_services
from ..utils.responses import ok
from ..utils.validators import BlockerCreate, BlockerUpdate, dump, object_id, optional_choice, parse_body

bp = Blueprint("blockers", __name__, url_prefix="/api/blockers")


@bp.get("")
@login_required
def list_blockers():
    status = optional_choice("status", BLOCKER_STATUSES)
    open_only = request.args.get("open", "").lower() in {"1", "true"}
    return ok(get_services().tracking.list_blockers(current_user_id(), status, open_only))


@bp.post("")
@login_required
def create():
    return ok(get_services().tracking.create_blocker(current_user_id(), dump(parse_body(BlockerCreate))), 201)


@bp.put("/<blocker_id>")
@login_required
def update(blocker_id: str):
    data = dump(parse_body(BlockerUpdate))
    return ok(get_services().tracking.update_blocker(current_user_id(), object_id(blocker_id, "blocker"), data))
