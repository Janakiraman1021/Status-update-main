from __future__ import annotations

from flask import Blueprint, request

from ..constants import WORK_CATEGORIES, WORK_STATUSES
from ..middleware.auth import current_user_id, login_required
from ..services import get_services
from ..utils.responses import ok
from ..utils.validators import object_id, optional_choice, optional_date_arg, pagination_args

bp = Blueprint("history", __name__, url_prefix="/api/history")

EOD_STATUSES = ["GENERATED", "SENT", "FAILED", "GENERATING", "SENDING"]


def _meta(page: int, limit: int, total: int) -> dict:
    return {"page": page, "limit": limit, "total": total, "pages": max(1, -(-total // limit))}


def _query() -> str | None:
    return (request.args.get("q") or "").strip()[:200] or None


@bp.get("/work")
@login_required
def work():
    page, limit = pagination_args()
    project = request.args.get("project_id") or None
    items, total = get_services().history.work(
        current_user_id(), page=page, limit=limit,
        date_from=optional_date_arg("from"), date_to=optional_date_arg("to"),
        project_id=str(object_id(project, "project")) if project else None,
        category=optional_choice("category", WORK_CATEGORIES), status=optional_choice("status", WORK_STATUSES),
        q=_query(),
    )
    return ok(items, meta=_meta(page, limit, total))


@bp.get("/eod")
@login_required
def eod():
    page, limit = pagination_args()
    rows, total = get_services().history.eods(
        current_user_id(), page=page, limit=limit,
        date_from=optional_date_arg("from"), date_to=optional_date_arg("to"),
        status=optional_choice("status", EOD_STATUSES), q=_query(),
    )
    return ok(rows, meta=_meta(page, limit, total))


@bp.get("/search")
@login_required
def search():
    return ok(get_services().history.search(current_user_id(), (request.args.get("q") or "")[:200]))


@bp.get("/summary")
@login_required
def summary():
    return ok(get_services().history.summarize(current_user_id(), optional_date_arg("from"), optional_date_arg("to")))
