"""End-to-end scenario from the specification (section 47), exercised through the HTTP API."""
from datetime import datetime, timezone

from conftest import PASSWORD, ApiClient, data


def test_full_workflow(app, services, mail):
    # 1. Create test user
    user = services.auth.create_user("Janakiraman", "e2e@example.com", PASSWORD)
    services.settings.update(user, {"auto_eod_enabled": True, "eod_time": "18:30", "timezone": "Asia/Kolkata", "eod_tone": "professional"})

    # 2. Login
    api = ApiClient(app.test_client())
    assert api.login("e2e@example.com").status_code == 200

    # 3. Select the date on the calendar
    date = "2026-10-03"
    calendar = data(api.get("/api/calendar?year=2026&month=10"))
    assert next(d for d in calendar["days"] if d["date"] == date)["has_work"] is False

    # 4. Create project
    project = data(api.post("/api/projects", {"name": "Samunnati Statements Dashboard"}))

    # 5. Add work entry (quick notes) for the day
    notes = ("Worked on Statements Dashboard.\nRemoved statement selector.\nAdded dark mode.\nImplemented date validation.\n"
             "Created access governance schema.\n94 tests passed.\nNeed DBA approval.")
    data(api.post("/api/work-logs", {"work_date": date, "project_id": project["id"], "quick_notes": notes}))

    # 6. Add completed item
    data(api.post("/api/work-items", {"work_date": date, "description": "Added date validation to the Repayment form",
                                      "category": "Enhancement", "status": "Completed", "time": "15:00"}))

    # 7. Add blocker
    data(api.post("/api/blockers", {"description": "Need confirmation on which date column should drive the Account Statement filter.",
                                    "identified_date": date, "project_id": project["id"]}))

    # 8. Save (state is persisted) — reload the day
    day = data(api.get(f"/api/work-logs/{date}"))
    assert day["log"]["quick_notes"] == notes
    assert day["summary"]["completed"] == 1 and day["summary"]["blockers"] == 1

    # 9. Generate EOD
    view = data(api.post("/api/eod/generate", {"work_date": date}))
    eod_id = view["report"]["id"]

    # 10. Verify generated report
    body = view["current"]["body"]
    assert view["report"]["subject"] == "EOD Status Update | 03 Oct 2026 | Samunnati Statements Dashboard"
    assert "Removed statement selector." in body and "94 tests passed." in body
    assert "Need confirmation on which date column" in body
    assert "Need DBA approval." in body
    assert view["current"]["warnings"] == []

    # 11. Edit report (one sentence)
    edited = body.replace("Added dark mode.", "Added light and dark mode support.")
    view = data(api.put(f"/api/eod/{eod_id}", {"body": edited}))
    assert view["report"]["current_version"] == 2

    # 12. Send email (mock provider)
    view = data(api.post(f"/api/eod/{eod_id}/send", {"recipients": {"to": ["manager@example.com"], "cc": [], "bcc": []}}))

    # 13. Verify email status
    assert view["report"]["status"] == "SENT"
    assert len(mail.sent) == 1 and "light and dark mode support" in mail.sent[0].text
    assert view["deliveries"][0]["success"] is True

    # 14. Run scheduler again (after EOD time)
    stats = services.scheduler.run_tick(datetime(2026, 10, 3, 13, 30, tzinfo=timezone.utc))

    # 15. Verify the second email was NOT sent
    assert stats == {"skipped_already_sent": 1}
    assert len(mail.sent) == 1

    # 16. Verify EOD history and calendar
    history = api.get("/api/history/eod").get_json()
    assert history["meta"]["total"] == 1
    assert history["data"][0]["status"] == "SENT" and history["data"][0]["id"] == eod_id
    day_state = next(d for d in data(api.get("/api/calendar?year=2026&month=10"))["days"] if d["date"] == date)
    assert day_state["has_work"] is True and day_state["eod_sent"] is True
