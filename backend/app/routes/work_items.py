from __future__ import annotations

from flask import Blueprint

from ..middleware.auth import current_user_id, login_required
from ..services import get_services
from ..services.ai_service import AIError
from ..utils.errors import AppError, ValidationFailed
from ..utils.responses import ok
from ..utils.validators import (
    CategorizeRequest, WorkItemBulkCreate, WorkItemCreate, WorkItemUpdate, dump, object_id, parse_body,
)

bp = Blueprint("work_items", __name__, url_prefix="/api/work-items")


@bp.post("")
@login_required
def create():
    return ok(get_services().work_logs.create_item(current_user_id(), dump(parse_body(WorkItemCreate))), 201)


@bp.post("/bulk")
@login_required
def create_bulk():
    body = parse_body(WorkItemBulkCreate)
    items = [item.model_dump(exclude_unset=True) for item in body.items]
    missing = [index for index, item in enumerate(items) if not item.get("description")]
    if missing:
        raise ValidationFailed("Every entry needs a description.", details={"items": missing})
    return ok(get_services().work_logs.create_items(current_user_id(), body.work_date, items), 201)


@bp.put("/<item_id>")
@login_required
def update(item_id: str):
    data = dump(parse_body(WorkItemUpdate))
    return ok(get_services().work_logs.update_item(current_user_id(), object_id(item_id, "work entry"), data))


@bp.delete("/<item_id>")
@login_required
def delete(item_id: str):
    get_services().work_logs.delete_item(current_user_id(), object_id(item_id, "work entry"))
    return ok({"deleted": True})


@bp.post("/categorize")
@login_required
def categorize():
    """AI suggestions only; nothing is saved until the user accepts them."""
    body = parse_body(CategorizeRequest)
    services = get_services()
    try:
        suggestions = services.ai.categorize(body.text)
    except AIError as exc:
        raise AppError(str(exc), code="AI_CATEGORIZE_FAILED", status_code=502) from exc
    return ok({"items": suggestions, "provider": services.ai.name})
