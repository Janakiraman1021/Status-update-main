from datetime import datetime, timezone

from app.utils.datetime_utils import default_entry_timestamp, format_time, local_today, month_bounds
from conftest import data


def test_local_today_respects_timezone():
    instant = datetime(2026, 10, 2, 20, 0, tzinfo=timezone.utc)  # 01:30 on 3 Oct in India
    assert local_today("Asia/Kolkata", instant) == "2026-10-03"
    assert local_today("America/New_York", instant) == "2026-10-02"


def test_default_entry_timestamp():
    now = datetime(2026, 10, 3, 6, 0, tzinfo=timezone.utc)
    assert default_entry_timestamp("2026-10-03", "Asia/Kolkata", now) == now
    backfilled = default_entry_timestamp("2026-10-01", "Asia/Kolkata", now)
    assert format_time(backfilled, "Asia/Kolkata") == "9:00 AM"


def test_month_bounds():
    assert month_bounds(2026, 2) == ("2026-02-01", "2026-02-28")
    assert month_bounds(2026, 12) == ("2026-12-01", "2026-12-31")


def test_calendar_reports_work_and_eod_state(api, mail):
    api.post("/api/work-items", {"work_date": "2026-10-03", "description": "Removed selector", "status": "Completed"})
    api.post("/api/work-logs", {"work_date": "2026-10-07", "quick_notes": "notes only"})
    api.post("/api/blockers", {"description": "Waiting", "identified_date": "2026-10-07"})
    eod_id = data(api.post("/api/eod/generate", {"work_date": "2026-10-03"}))["report"]["id"]
    eod_view = data(api.get(f"/api/eod/{eod_id}"))
    assert eod_view["source_inputs"]["entries"][0]["description"] == "Removed selector"
    api.post(f"/api/eod/{eod_id}/send")

    cal = data(api.get("/api/calendar?year=2026&month=10"))
    assert len(cal["days"]) == 31
    by_date = {d["date"]: d for d in cal["days"]}
    assert by_date["2026-10-03"] == {"date": "2026-10-03", "is_holiday": False, "has_work": True, "eod_status": "SENT", "eod_generated": True,
                                     "eod_sent": True, "eod_failed": False, "has_blocker": False}
    assert by_date["2026-10-07"]["has_work"] is True and by_date["2026-10-07"]["has_blocker"] is True
    assert by_date["2026-10-07"]["eod_generated"] is False
    assert data(api.get("/api/eod/2026-10-07"))["source_inputs"]["quick_notes"] == "notes only"
    assert by_date["2026-10-10"]["has_work"] is False
    assert api.get("/api/calendar?year=2026&month=13").status_code == 400
    assert api.get("/api/calendar?year=abc&month=1").status_code == 400


def test_calendar_marks_sundays_and_second_fourth_saturdays_as_holidays(api):
    for year, month in ((2026, 10), (2026, 11), (2027, 2)):
        calendar = data(api.get(f"/api/calendar?year={year}&month={month}"))
        expected_holidays = {
            day["date"] for day in calendar["days"]
            if datetime.fromisoformat(day["date"]).weekday() == 6
            or (
                datetime.fromisoformat(day["date"]).weekday() == 5
                and (datetime.fromisoformat(day["date"]).day - 1) // 7 + 1 in (2, 4)
            )
        }
        holiday_dates = {day["date"] for day in calendar["days"] if day["is_holiday"]}
        assert holiday_dates == expected_holidays

    october = data(api.get("/api/calendar?year=2026&month=10"))
    october_holidays = {day["date"] for day in october["days"] if day["is_holiday"]}
    assert {"2026-10-11", "2026-10-25", "2026-10-10", "2026-10-24"} <= october_holidays
    november = data(api.get("/api/calendar?year=2026&month=11"))
    november_holidays = {day["date"] for day in november["days"] if day["is_holiday"]}
    assert {"2026-11-14", "2026-11-28"} <= november_holidays
    february = data(api.get("/api/calendar?year=2027&month=2"))
    february_holidays = {day["date"] for day in february["days"] if day["is_holiday"]}
    assert {"2027-02-14", "2027-02-28", "2027-02-13", "2027-02-27"} <= february_holidays


def test_dashboard_uses_real_data(api, today):
    empty = data(api.get("/api/dashboard"))
    assert empty["summary"]["total_entries"] == 0 and empty["eod"]["status"] == "NOT_GENERATED"
    assert empty["user_name"] == "Janakiraman" and empty["today"] == today
    for status in ("Completed", "Completed", "In Progress"):
        api.post("/api/work-items", {"work_date": today, "description": f"{status} item", "status": status})
    api.post("/api/blockers", {"description": "DB access", "identified_date": today})
    dash = data(api.get("/api/dashboard"))
    assert dash["summary"]["completed"] == 2 and dash["summary"]["in_progress"] == 1 and dash["summary"]["blockers"] == 1
    assert len(dash["recent_activity"]) == 3 and dash["open_blocker_count"] == 1
    assert dash["days_logged_this_week"] == 1


def _seed_history(api):
    project = data(api.post("/api/projects", {"name": "Azure Platform"}))
    for day in range(1, 26):
        api.post("/api/work-items", {"work_date": f"2026-09-{day:02d}", "description": f"Task number {day}", "category": "Development", "status": "Completed"})
    api.post("/api/work-items", {"work_date": "2026-09-27", "description": "Set up pipeline", "project_id": project["id"], "category": "Deployment"})
    api.post("/api/work-logs", {"work_date": "2026-09-28", "next_steps": "Move Azure functions to premium plan"})
    api.post("/api/blockers", {"description": "Azure subscription quota", "identified_date": "2026-09-28"})
    return project


def test_work_history_pagination_and_filters(api):
    project = _seed_history(api)
    page1 = api.get("/api/history/work?page=1&limit=10").get_json()
    assert page1["meta"] == {"page": 1, "limit": 10, "total": 26, "pages": 3}
    assert page1["data"][0]["work_date"] == "2026-09-27"  # newest first
    assert len(api.get("/api/history/work?page=3&limit=10").get_json()["data"]) == 6
    assert api.get("/api/history/work?limit=1000").get_json()["meta"]["limit"] == 100

    assert data(api.get("/api/history/work?category=Deployment"))[0]["description"] == "Set up pipeline"
    assert data(api.get(f"/api/history/work?project_id={project['id']}"))[0]["project_name"] == "Azure Platform"
    assert len(data(api.get("/api/history/work?from=2026-09-10&to=2026-09-12"))) == 3
    assert api.get("/api/history/work?from=2026-09-12&to=2026-09-10").status_code == 400
    assert api.get("/api/history/work?status=Meh").status_code == 400


def test_search_is_server_side_and_escaped(api):
    _seed_history(api)
    # Matching a project name returns that project's entries
    assert [i["description"] for i in data(api.get("/api/history/work?q=azure"))] == ["Set up pipeline"]
    assert data(api.get("/api/history/work?q=Task number 1"))  # substring match
    assert data(api.get("/api/history/work?q=.*")) == []  # regex metacharacters are escaped
    results = data(api.get("/api/history/search?q=Azure"))
    assert results["notes"][0]["field"] == "next_steps"
    assert results["blockers"][0]["description"] == "Azure subscription quota"
    assert results["projects"][0]["name"] == "Azure Platform"
    assert api.get("/api/history/search?q=a").status_code == 400


def test_eod_history(api):
    api.post("/api/work-logs", {"work_date": "2026-10-01", "quick_notes": "did things"})
    api.post("/api/work-logs", {"work_date": "2026-10-02", "quick_notes": "more things"})
    first = data(api.post("/api/eod/generate", {"work_date": "2026-10-01"}))["report"]["id"]
    data(api.post("/api/eod/generate", {"work_date": "2026-10-02"}))
    api.post(f"/api/eod/{first}/send")
    rows = api.get("/api/history/eod").get_json()
    assert rows["meta"]["total"] == 2
    assert [r["status"] for r in rows["data"]] == ["GENERATED", "SENT"]
    assert rows["data"][1]["sent_time_label"]
    assert len(data(api.get("/api/history/eod?status=SENT"))) == 1


def test_period_summary(api):
    _seed_history(api)
    result = data(api.get("/api/history/summary?from=2026-09-20&to=2026-09-28"))
    assert result["entry_count"] == 7 and "Set up pipeline" in result["summary"]
    assert api.get("/api/history/summary?from=2026-01-01&to=2026-09-28").status_code == 400


def test_settings_roundtrip_and_validation(api):
    settings = data(api.get("/api/settings"))
    assert settings["preferences"]["timezone"] == "Asia/Kolkata"
    assert settings["preferences"]["eod_time"] == "18:30"
    assert settings["ai"]["provider"] == "local"
    assert "password" not in str(settings["email"]).lower()

    updated = data(api.put("/api/settings", {"name": "Janakiraman K", "eod_time": "19:00", "auto_eod_enabled": True,
                                             "theme": "dark", "timezone": "Europe/London"}))
    assert updated["profile"]["name"] == "Janakiraman K"
    assert updated["preferences"]["eod_time"] == "19:00" and updated["preferences"]["theme"] == "dark"
    for bad in ({"eod_time": "7pm"}, {"timezone": "Mars/Olympus"}, {"theme": "neon"}, {"reminder_minutes_before": 1},
                {"recipients": {"to": ["bad"]}}, {"default_project_id": "507f1f77bcf86cd799439011"}):
        assert api.put("/api/settings", bad).status_code == 400, bad


def test_test_email(api, mail):
    result = data(api.post("/api/email/test", {}))
    assert result["sent"] is True and mail.sent[0].subject == "WorkLog test email"
    mail.fail_with = "boom"
    assert api.post("/api/email/test", {}).status_code == 502
