from __future__ import annotations

from flask import Blueprint, request

from ..constants import DEPENDENCY_STATUSES, DEPENDENCY_TYPES
from ..middleware.auth import current_user_id, login_required
from ..services import get_services
from ..utils.responses import ok
from ..utils.validators import DependencyCreate, DependencyUpdate, dump, object_id, optional_choice, parse_body

bp = Blueprint("dependencies", __name__, url_prefix="/api/dependencies")


@bp.get("")
@login_required
def list_dependencies():
    status = optional_choice("status", DEPENDENCY_STATUSES)
    type_ = optional_choice("type", DEPENDENCY_TYPES)
    open_only = request.args.get("open", "").lower() in {"1", "true"}
    return ok(get_services().tracking.list_dependencies(current_user_id(), status, type_, open_only))


@bp.post("")
@login_required
def create():
    return ok(get_services().tracking.create_dependency(current_user_id(), dump(parse_body(DependencyCreate))), 201)


@bp.put("/<dep_id>")
@login_required
def update(dep_id: str):
    data = dump(parse_body(DependencyUpdate))
    return ok(get_services().tracking.update_dependency(current_user_id(), object_id(dep_id, "dependency"), data))
