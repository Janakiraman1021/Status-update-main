import re

import pytest

from app.services.ai_service import AIError, EodDraft
from conftest import data

DATE = "2026-10-03"
NOTES = ("Worked on Statements Dashboard.\nRemoved statement selector.\nAdded dark mode.\n"
         "Implemented date validation.\nCreated access governance schema.\n94 tests passed.\nNeed DBA approval.")


@pytest.fixture
def logged_day(api):
    project = data(api.post("/api/projects", {"name": "Statements Dashboard"}))
    api.post("/api/work-logs", {"work_date": DATE, "project_id": project["id"], "quick_notes": NOTES})
    api.put("/api/settings", {"eod_tone": "professional"})  # exact-wording assertions below
    return project


def _generate(api, date=DATE):
    response = api.post("/api/eod/generate", {"work_date": date})
    assert response.status_code == 201, response.get_json()
    return data(response)


def test_generate_requires_logged_work(api):
    response = api.post("/api/eod/generate", {"work_date": DATE})
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "NO_WORK_LOGGED"


def test_generate_creates_structured_report(api, logged_day):
    view = _generate(api)
    report, current = view["report"], view["current"]
    assert report["status"] == "GENERATED"
    assert report["current_version"] == 1
    assert report["subject"] == "EOD Status Update | 03 Oct 2026 | Statements Dashboard"
    body = current["body"]
    assert body.startswith("Hi,\n\nTrust you are doing well.")
    for heading in ("EXECUTIVE SNAPSHOT", "KEY DELIVERABLES", "QUALITY ASSURANCE AND VALIDATION", "ASKS / APPROVALS"):
        assert heading in body
    assert "- 94 tests passed." in body
    assert "- Need DBA approval." in body
    assert body.rstrip().endswith("Thanks and regards,\nJanakiraman")
    # Sections without information are omitted
    assert "NEXT STEPS" not in body and "BLOCKERS / DEPENDENCIES" not in body
    assert view["versions"][0]["source"] == "generated"
    assert current["warnings"] == []


def test_generation_options_default_from_settings_and_can_be_overridden(api, logged_day):
    api.put("/api/settings", {"eod_length": "long", "eod_tone": "professional"})
    view = _generate(api)
    assert view["report"]["options"] == {"length": "long", "tone": "professional"}
    eod_id = view["report"]["id"]
    view = data(api.post(f"/api/eod/{eod_id}/regenerate", {"length": "short", "tone": "executive"}))
    assert view["report"]["options"] == {"length": "short", "tone": "executive"}
    assert view["versions"][0]["options"] == {"length": "short", "tone": "executive"}
    assert api.post(f"/api/eod/{eod_id}/regenerate", {"length": "huge"}).status_code == 400


def test_regenerate_keeps_previous_versions(api, services, user, logged_day):
    first = _generate(api)
    eod_id = first["report"]["id"]
    second = data(api.post(f"/api/eod/{eod_id}/regenerate"))
    assert second["report"]["current_version"] == 2
    assert [v["version"] for v in second["versions"]] == [2, 1]
    assert [v["is_current"] for v in second["versions"]] == [True, False]
    assert second["versions"][0]["source"] == "regenerated"
    assert services.repos.eod_versions.col.count_documents({"user_id": user["_id"]}) == 2
    assert services.repos.eods.col.count_documents({"user_id": user["_id"]}) == 1


def test_edit_creates_version_then_updates_in_place(api, logged_day):
    eod_id = _generate(api)["report"]["id"]
    current = data(api.get(f"/api/eod/{eod_id}"))["current"]
    edited_body = current["body"].replace("Added dark mode.", "Added light and dark mode support.")
    view = data(api.put(f"/api/eod/{eod_id}", {"body": edited_body}))
    assert view["report"]["current_version"] == 2
    assert view["current"]["source"] == "edited"
    assert "light and dark mode support" in view["current"]["body"]

    view = data(api.put(f"/api/eod/{eod_id}", {"subject": "EOD Status Update | 03 Oct 2026 | Dashboard"}))
    assert view["report"]["current_version"] == 2  # consecutive unsent edits do not pile up versions
    assert view["current"]["subject"].endswith("Dashboard")
    v1 = data(api.get(f"/api/eod/{eod_id}/versions/1"))
    assert "Added dark mode." in v1["body"]  # generated version untouched


def test_edit_validation(api, logged_day):
    eod_id = _generate(api)["report"]["id"]
    assert api.put(f"/api/eod/{eod_id}", {"body": "   "}).status_code == 400
    assert api.put(f"/api/eod/{eod_id}", {}).status_code == 400
    assert api.put(f"/api/eod/{eod_id}", {"recipients": {"to": ["not-an-email"]}}).status_code == 400


def test_send_eod(api, mail, logged_day):
    eod_id = _generate(api)["report"]["id"]
    view = data(api.post(f"/api/eod/{eod_id}/send", {"recipients": {"to": ["manager@example.com"], "cc": ["lead@example.com"], "bcc": []}}))
    assert view["report"]["status"] == "SENT"
    assert view["report"]["sent_version"] == 1
    assert view["report"]["sent_at"]
    assert view["deliveries"][0]["success"] is True
    assert len(mail.sent) == 1
    email = mail.sent[0]
    assert email.to == ["manager@example.com"] and email.cc == ["lead@example.com"]
    assert email.subject == "EOD Status Update | 03 Oct 2026 | Statements Dashboard"
    assert ">Key Deliverables</h3>" in email.html and "<li" in email.html  # plain headings + bullets
    assert "Prepared by" not in email.html and "<table" not in email.html  # no template decoration
    assert "**" not in email.html and "##" not in email.html  # no raw markdown
    assert email.text.startswith("Hi,")
    assert email.reply_to == "demo@example.com"


def test_send_defaults_to_user_email_without_recipients(api, mail, logged_day):
    eod_id = _generate(api)["report"]["id"]
    data(api.post(f"/api/eod/{eod_id}/send"))
    assert mail.sent[0].to == ["demo@example.com"]


def test_send_uses_default_recipients_from_settings(api, mail, logged_day):
    api.put("/api/settings", {"recipients": {"to": ["team@example.com"], "cc": [], "bcc": ["archive@example.com"]}})
    eod_id = _generate(api)["report"]["id"]
    data(api.post(f"/api/eod/{eod_id}/send"))
    assert mail.sent[0].to == ["team@example.com"] and mail.sent[0].bcc == ["archive@example.com"]


def test_cannot_send_twice(api, mail, logged_day):
    eod_id = _generate(api)["report"]["id"]
    data(api.post(f"/api/eod/{eod_id}/send"))
    response = api.post(f"/api/eod/{eod_id}/send")
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "EOD_ALREADY_SENT"
    assert len(mail.sent) == 1


def test_explicit_resend(api, mail, logged_day):
    eod_id = _generate(api)["report"]["id"]
    data(api.post(f"/api/eod/{eod_id}/send"))
    view = data(api.post(f"/api/eod/{eod_id}/send", {"resend": True}))
    assert view["report"]["status"] == "SENT"
    assert len(mail.sent) == 2


def test_email_failure_marks_failed_and_retry_succeeds(api, mail, logged_day):
    eod_id = _generate(api)["report"]["id"]
    mail.fail_with = "SMTP authentication failed."
    response = api.post(f"/api/eod/{eod_id}/send")
    assert response.status_code == 502
    error = response.get_json()["error"]
    assert error["code"] == "EMAIL_FAILED" and error["message"] == "Unable to send EOD. Retry."
    view = data(api.get(f"/api/eod/{eod_id}"))
    assert view["report"]["status"] == "FAILED"
    assert view["report"]["last_error"]["code"] == "EMAIL_FAILED"
    assert view["report"]["current_version"] == 1  # no duplicate report generated

    mail.fail_with = None
    view = data(api.post(f"/api/eod/{eod_id}/send"))
    assert view["report"]["status"] == "SENT" and view["report"]["last_error"] is None
    assert [d["success"] for d in view["deliveries"]] == [True, False]


def test_edit_after_send_preserves_sent_version(api, mail, logged_day):
    eod_id = _generate(api)["report"]["id"]
    sent = data(api.post(f"/api/eod/{eod_id}/send"))
    sent_body = sent["current"]["body"]
    view = data(api.put(f"/api/eod/{eod_id}", {"body": sent_body + "\nP.S. corrected later."}))
    assert view["report"]["status"] == "SENT"
    assert view["report"]["current_version"] == 2
    assert view["report"]["sent_version"] == 1
    assert view["report"]["has_unsent_changes"] is True
    original = data(api.get(f"/api/eod/{eod_id}/versions/1"))
    assert original["body"] == sent_body and original["sent_at"]
    assert view["current"]["created_by"] == view["report"]["user_id"]
    # A second edit after sending still never touches the sent version
    data(api.put(f"/api/eod/{eod_id}", {"body": sent_body + "\nP.P.S."}))
    assert data(api.get(f"/api/eod/{eod_id}/versions/1"))["body"] == sent_body


def test_ai_failure_marks_generation_failed_and_allows_retry(api, app, logged_day, monkeypatch):
    runtime = app.extensions["worklog_runtime"]
    original = runtime.ai.generate_eod

    def boom(context, style="standard"):
        raise AIError("The AI provider is rate limiting requests. Please retry shortly.")

    monkeypatch.setattr(runtime.ai, "generate_eod", boom)
    response = api.post("/api/eod/generate", {"work_date": DATE})
    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == "EOD_GENERATION_FAILED"
    view = data(api.get(f"/api/eod/{DATE}"))
    assert view["report"]["status"] == "FAILED"
    assert view["report"]["last_error"]["stage"] == "GENERATION"
    assert api.post(f"/api/eod/{view['report']['id']}/send").status_code == 409  # nothing to send

    monkeypatch.setattr(runtime.ai, "generate_eod", original)
    view = _generate(api)
    assert view["report"]["status"] == "GENERATED" and view["report"]["current_version"] == 1


def test_regenerate_failure_keeps_existing_version(api, app, logged_day, monkeypatch):
    eod_id = _generate(api)["report"]["id"]
    monkeypatch.setattr(app.extensions["worklog_runtime"].ai, "generate_eod",
                        lambda c, style="standard": (_ for _ in ()).throw(AIError("down")))
    assert api.post(f"/api/eod/{eod_id}/regenerate").status_code == 502
    view = data(api.get(f"/api/eod/{eod_id}"))
    assert view["report"]["status"] == "GENERATED" and view["report"]["current_version"] == 1


def test_fabricated_numbers_are_flagged(api, app, logged_day, monkeypatch):
    monkeypatch.setattr(app.extensions["worklog_runtime"].ai, "generate_eod",
                        lambda c, style="standard": EodDraft(executive_snapshot="Delivered 3 features; 95 tests passed.",
                                                             key_deliverables=["Removed statement selector."]))
    view = _generate(api)
    warnings = view["report"]["warnings"]
    assert any("'3'" in w for w in warnings) and any("'95'" in w for w in warnings)


def test_outdated_flag_after_new_work(api, logged_day):
    eod_id = _generate(api)["report"]["id"]
    assert data(api.get(f"/api/eod/{eod_id}"))["outdated"] is False
    api.post("/api/work-items", {"work_date": DATE, "description": "Late fix", "status": "Completed"})
    assert data(api.get(f"/api/eod/{eod_id}"))["outdated"] is True


def test_eod_lookup_by_date_and_id(api, logged_day):
    assert data(api.get("/api/eod/2026-10-04"))["report"] is None
    eod_id = _generate(api)["report"]["id"]
    assert data(api.get(f"/api/eod/{DATE}"))["report"]["id"] == eod_id
    assert data(api.get(f"/api/eod/{eod_id}"))["work_date"] == DATE
    assert api.get("/api/eod/nonsense").status_code == 404


def test_preview_html(api, logged_day):
    eod_id = _generate(api)["report"]["id"]
    response = api.get(f"/api/eod/{eod_id}/preview")
    assert response.status_code == 200 and response.mimetype == "text/html"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert re.search(r"<h3[^>]*>Executive Snapshot</h3>", response.get_data(as_text=True))


def test_other_user_cannot_touch_eod(api, other_api, logged_day):
    eod_id = _generate(api)["report"]["id"]
    assert other_api.get(f"/api/eod/{eod_id}").status_code == 404
    assert other_api.post(f"/api/eod/{eod_id}/send").status_code == 404
    assert other_api.put(f"/api/eod/{eod_id}", {"body": "hijack"}).status_code == 404
    assert other_api.post(f"/api/eod/{eod_id}/regenerate").status_code == 404
