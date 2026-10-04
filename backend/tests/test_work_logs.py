from conftest import data

DATE = "2026-10-03"


def _project(api, name="Samunnati Statements Dashboard"):
    return data(api.post("/api/projects", {"name": name}))


def test_empty_day(api):
    day = data(api.get(f"/api/work-logs/{DATE}"))
    assert day["log"] is None
    assert day["entries"] == []
    assert day["summary"]["total_entries"] == 0
    assert day["eod"]["status"] == "NOT_GENERATED"
    assert day["date_label"] == "03 October 2026"


def test_invalid_dates_rejected(api):
    assert api.get("/api/work-logs/2026-13-45").status_code == 400
    assert api.get("/api/work-logs/yesterday").status_code == 400
    assert api.post("/api/work-logs", {"work_date": "2026-02-30", "quick_notes": "x"}).status_code == 400


def test_upsert_work_log_is_idempotent_per_date(api, services, user):
    project = _project(api)
    first = data(api.post("/api/work-logs", {"work_date": DATE, "quick_notes": "removed selector", "project_id": project["id"]}))
    second = data(api.post("/api/work-logs", {"work_date": DATE, "quick_notes": "removed selector\nadded dark mode"}))
    assert first["id"] == second["id"]
    assert second["project_id"] == project["id"]  # untouched fields are preserved
    assert services.repos.work_logs.col.count_documents({"user_id": user["_id"], "work_date": DATE}) == 1
    day = data(api.get(f"/api/work-logs/{DATE}"))
    assert day["log"]["quick_notes"] == "removed selector\nadded dark mode"
    assert day["project_name"] == "Samunnati Statements Dashboard"
    assert day["has_work"] is True


def test_entries_are_chronological_and_not_overwritten(api):
    for time, text in (("15:00", "Implemented dark mode"), ("10:00", "Started working on dashboard"), ("12:00", "Removed statement selector")):
        assert api.post("/api/work-items", {"work_date": DATE, "description": text, "time": time, "status": "Completed"}).status_code == 201
    day = data(api.get(f"/api/work-logs/{DATE}"))
    assert [e["description"] for e in day["entries"]] == [
        "Started working on dashboard", "Removed statement selector", "Implemented dark mode",
    ]
    assert [e["time_label"] for e in day["entries"]] == ["10:00 AM", "12:00 PM", "3:00 PM"]
    assert day["summary"]["completed"] == 3


def test_entry_timestamps_are_stored_in_utc(api, services, user):
    item = data(api.post("/api/work-items", {"work_date": DATE, "description": "Morning work", "time": "10:00"}))
    stored = services.repos.work_items.col.find_one({"description": "Morning work"})
    assert stored["timestamp"].utcoffset().total_seconds() == 0
    assert stored["timestamp"].hour == 4 and stored["timestamp"].minute == 30  # 10:00 IST == 04:30 UTC
    assert item["time"] == "10:00"


def test_edit_and_delete_entry(api):
    item = data(api.post("/api/work-items", {"work_date": DATE, "description": "fix date validaton"}))
    updated = data(api.put(f"/api/work-items/{item['id']}", {"description": "Fixed date validation", "category": "Bug Fix", "status": "Completed"}))
    assert updated["description"] == "Fixed date validation"
    assert updated["category"] == "Bug Fix"
    assert api.delete(f"/api/work-items/{item['id']}").status_code == 200
    assert api.delete(f"/api/work-items/{item['id']}").status_code == 404


def test_entry_validation(api):
    assert api.post("/api/work-items", {"work_date": DATE, "description": "   "}).status_code == 400
    assert api.post("/api/work-items", {"work_date": DATE, "description": "x", "category": "Gaming"}).status_code == 400
    assert api.post("/api/work-items", {"work_date": DATE, "description": "x", "status": "Done-ish"}).status_code == 400
    assert api.post("/api/work-items", {"work_date": DATE, "description": "x", "time": "25:00"}).status_code == 400
    assert api.post("/api/work-items", {"work_date": DATE, "description": "x", "project_id": "not-an-id"}).status_code == 400
    assert api.post("/api/work-items", {"work_date": DATE, "description": "x", "unexpected": 1}).status_code == 400


def test_new_day_uses_default_project(api):
    project = _project(api)
    api.put("/api/settings", {"default_project_id": project["id"]})
    log = data(api.post("/api/work-logs", {"work_date": DATE, "quick_notes": "notes"}))
    assert log["project_id"] == project["id"]
    # An explicit choice (including clearing it) is respected afterwards
    cleared = data(api.post("/api/work-logs", {"work_date": DATE, "project_id": None}))
    assert cleared["project_id"] is None
    assert data(api.post("/api/work-logs", {"work_date": DATE, "quick_notes": "more"}))["project_id"] is None


def test_entries_inherit_day_project(api):
    project = _project(api)
    api.post("/api/work-logs", {"work_date": DATE, "project_id": project["id"]})
    item = data(api.post("/api/work-items", {"work_date": DATE, "description": "Created access governance schema"}))
    assert item["project_name"] == "Samunnati Statements Dashboard"


def test_bulk_create(api):
    created = data(api.post("/api/work-items/bulk", {"work_date": DATE, "items": [
        {"description": "Removed selector", "status": "Completed"}, {"description": "Dark mode", "status": "In Progress"},
    ]}))
    assert len(created) == 2


def test_users_cannot_access_each_others_data(api, other_api):
    item = data(api.post("/api/work-items", {"work_date": DATE, "description": "Private work"}))
    log = data(api.post("/api/work-logs", {"work_date": DATE, "quick_notes": "private notes"}))
    project = _project(api)

    assert data(other_api.get(f"/api/work-logs/{DATE}"))["entries"] == []
    assert other_api.put(f"/api/work-items/{item['id']}", {"description": "hijack"}).status_code == 404
    assert other_api.delete(f"/api/work-items/{item['id']}").status_code == 404
    assert other_api.put(f"/api/work-logs/{log['id']}", {"quick_notes": "hijack"}).status_code == 404
    assert other_api.get(f"/api/projects/{project['id']}").status_code == 404
    # Referencing someone else's project is rejected
    assert other_api.post("/api/work-items", {"work_date": DATE, "description": "x", "project_id": project["id"]}).status_code == 400
    assert data(api.get(f"/api/work-logs/{DATE}"))["entries"][0]["description"] == "Private work"


def test_categorize_suggestions(api):
    result = data(api.post("/api/work-items/categorize", {"text": "fixed date validation\ninvestigating azure deployment\n94 tests passed"}))
    items = result["items"]
    assert [i["description"] for i in items] == ["Fixed date validation", "Investigating azure deployment", "94 tests passed"]
    assert items[0]["category"] == "Bug Fix" and items[0]["status"] == "Completed"
    assert items[1]["status"] == "In Progress"
    assert items[2]["category"] == "Testing"


def test_delete_work_log_keeps_entries(api):
    log = data(api.post("/api/work-logs", {"work_date": DATE, "quick_notes": "notes"}))
    api.post("/api/work-items", {"work_date": DATE, "description": "Entry stays"})
    assert api.delete(f"/api/work-logs/{log['id']}").status_code == 200
    day = data(api.get(f"/api/work-logs/{DATE}"))
    assert day["log"] is None and len(day["entries"]) == 1
