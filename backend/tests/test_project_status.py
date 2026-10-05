from conftest import data


def test_project_status_is_saved_per_project_and_date(api):
    project = data(api.post("/api/projects", {"name": "Website refresh"}))
    payload = {
        "project_id": project["id"],
        "work_date": "2026-10-05",
        "status": "Needs help",
        "daily_update": "Finished the sign-in page.",
        "next_step": "Connect it to the API.",
        "help_needed": "Need the test account details.",
    }

    saved = data(api.post("/api/project-statuses", payload))
    assert saved["status"] == "Needs help"
    assert saved["daily_update"] == "Finished the sign-in page."
    assert saved["project_id"] == project["id"]

    loaded = data(api.get(f"/api/project-statuses?project_id={project['id']}&work_date=2026-10-05"))
    assert loaded["id"] == saved["id"]
    assert loaded["help_needed"] == "Need the test account details."

    updated = data(api.post("/api/project-statuses", {**payload, "status": "On track", "daily_update": "Sign-in page is ready."}))
    assert updated["id"] == saved["id"]
    assert updated["status"] == "On track"
    assert len(data(api.get(f"/api/project-statuses?project_id={project['id']}"))) == 1


def test_project_status_rejects_invalid_values(api):
    project = data(api.post("/api/projects", {"name": "Mobile app"}))
    base = {"project_id": project["id"], "work_date": "2026-10-05", "daily_update": "Fixed a crash"}

    assert api.post("/api/project-statuses", {**base, "status": "Excellent"}).status_code == 400
    assert api.post("/api/project-statuses", {**base, "work_date": "not-a-date"}).status_code == 400
    assert api.post("/api/project-statuses", {**base, "daily_update": "  "}).status_code == 400
    assert api.get(f"/api/project-statuses?project_id={project['id']}&work_date=not-a-date").status_code == 400
