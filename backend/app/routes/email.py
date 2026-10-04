from __future__ import annotations

import html

from flask import Blueprint, request

from ..middleware.auth import current_user, login_required
from ..services import get_services
from ..services.email_service import OutgoingEmail
from ..utils.errors import AppError
from ..utils.responses import ok
from ..utils.validators import TestEmailRequest, parse_body

bp = Blueprint("email", __name__, url_prefix="/api/email")


@bp.get("/status")
@login_required
def status():
    services = get_services()
    recent = services.repos.email_logs.recent(current_user()["_id"], 10)
    return ok({**services.email.status(), "recent": recent})


@bp.post("/test")
@login_required
def test_email():
    body = parse_body(TestEmailRequest) if request.get_data() else TestEmailRequest()
    user = current_user()
    services = get_services()
    connection = services.email.test_connection()
    if not connection.success:
        raise AppError(connection.error or "Email connection failed.", code="EMAIL_CONNECTION_FAILED", status_code=502)
    to = str(body.to or user["email"])
    message = "This is a test email from WorkLog. Your email configuration works."
    result = services.email.send_email(OutgoingEmail(
        to=[to],
        subject="WorkLog test email",
        text=f"Hi {user['name']},\n\n{message}\n",
        html=f"<p>Hi {html.escape(user['name'])},</p><p>{message}</p>",
    ), user_id=user["_id"], kind="test")
    if not result.success:
        raise AppError(result.error or "Test email failed.", code="EMAIL_FAILED", status_code=502)
    return ok({"sent": True, "to": to, "provider": services.email.status()["provider"]})
