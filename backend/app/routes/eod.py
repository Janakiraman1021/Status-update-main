from __future__ import annotations

from flask import Blueprint, Response, request

from ..middleware.auth import current_user, login_required
from ..services import get_services
from ..utils.errors import ValidationFailed
from ..utils.responses import ok
from ..utils.validators import EodGenerate, EodOptions, EodSend, EodUpdate, dump, object_id, parse_body

bp = Blueprint("eod", __name__, url_prefix="/api/eod")


@bp.post("/generate")
@login_required
def generate():
    body = parse_body(EodGenerate)
    services = get_services()
    services.eod.generate(current_user(), body.work_date, options={"length": body.length, "tone": body.tone})
    return ok(services.eod.view(current_user(), body.work_date), 201)


@bp.get("/<key>")
@login_required
def get_eod(key: str):
    """`key` is either a work date (YYYY-MM-DD) or a report id."""
    return ok(get_services().eod.view(current_user(), key))


@bp.put("/<eod_id>")
@login_required
def update(eod_id: str):
    data = dump(parse_body(EodUpdate))
    if not data:
        raise ValidationFailed("Nothing to update.")
    services = get_services()
    report = services.eod.update(current_user(), object_id(eod_id, "EOD report"), data)
    return ok(services.eod.view(current_user(), str(report["_id"])))


@bp.post("/<eod_id>/regenerate")
@login_required
def regenerate(eod_id: str):
    body = parse_body(EodOptions) if request.get_data() else EodOptions()
    services = get_services()
    report = services.eod.regenerate(current_user(), object_id(eod_id, "EOD report"), options={"length": body.length, "tone": body.tone})
    return ok(services.eod.view(current_user(), str(report["_id"])))


@bp.post("/<eod_id>/send")
@login_required
def send(eod_id: str):
    body = parse_body(EodSend)
    recipients = body.recipients.model_dump() if body.recipients else None
    services = get_services()
    report = services.eod.send(current_user(), object_id(eod_id, "EOD report"), recipients, resend=body.resend)
    return ok(services.eod.view(current_user(), str(report["_id"])))


@bp.get("/<eod_id>/versions/<int:version>")
@login_required
def version(eod_id: str, version: int):
    return ok(get_services().eod.version_detail(current_user(), object_id(eod_id, "EOD report"), version))


@bp.get("/<eod_id>/preview")
@login_required
def preview(eod_id: str):
    html = get_services().eod.preview_html(current_user(), object_id(eod_id, "EOD report"))
    response = Response(html, mimetype="text/html")
    response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
    return response
