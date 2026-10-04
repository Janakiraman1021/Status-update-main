from __future__ import annotations

from flask import Blueprint, request

from ..middleware.auth import current_user_id, login_required
from ..services import get_services
from ..utils.responses import ok
from ..utils.validators import ProjectCreate, ProjectUpdate, dump, object_id, parse_body

bp = Blueprint("projects", __name__, url_prefix="/api/projects")


@bp.get("")
@login_required
def list_projects():
    include_archived = request.args.get("include_archived", "false").lower() in {"1", "true", "yes"}
    return ok(get_services().projects.list(current_user_id(), include_archived))


@bp.get("/<project_id>")
@login_required
def get_project(project_id: str):
    return ok(get_services().projects.get(current_user_id(), object_id(project_id, "project")))


@bp.post("")
@login_required
def create():
    body = parse_body(ProjectCreate)
    return ok(get_services().projects.create(current_user_id(), body.name, body.description), 201)


@bp.put("/<project_id>")
@login_required
def update(project_id: str):
    data = dump(parse_body(ProjectUpdate))
    return ok(get_services().projects.update(current_user_id(), object_id(project_id, "project"), data))


@bp.post("/<project_id>/archive")
@login_required
def archive(project_id: str):
    return ok(get_services().projects.archive(current_user_id(), object_id(project_id, "project")))
