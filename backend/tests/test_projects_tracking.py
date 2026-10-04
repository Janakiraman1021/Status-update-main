from conftest import data

DATE = "2026-10-03"


def test_project_crud_and_archive(api):
    project = data(api.post("/api/projects", {"name": "  Mail   Classification System ", "description": "Inbox triage"}))
    assert project["name"] == "Mail Classification System"
    assert project["status"] == "Active"

    assert api.post("/api/projects", {"name": "mail classification system"}).status_code == 409

    renamed = data(api.put(f"/api/projects/{project['id']}", {"name": "Mail Classifier"}))
    assert renamed["name"] == "Mail Classifier"

    api.post("/api/work-items", {"work_date": DATE, "description": "Trained model", "project_id": project["id"]})
    archived = data(api.post(f"/api/projects/{project['id']}/archive"))
    assert archived["status"] == "Archived" and archived["archived_at"]

    assert data(api.get("/api/projects")) == []
    all_projects = data(api.get("/api/projects?include_archived=true"))
    assert all_projects[0]["entry_count"] == 1

    # Historical entries keep their project; new entries cannot use an archived project
    assert data(api.get(f"/api/work-logs/{DATE}"))["entries"][0]["project_name"] == "Mail Classifier"
    assert api.post("/api/work-items", {"work_date": DATE, "description": "x", "project_id": project["id"]}).status_code == 400

    restored = data(api.put(f"/api/projects/{project['id']}", {"status": "Active"}))
    assert restored["status"] == "Active" and restored["archived_at"] is None


def test_projects_cannot_be_deleted(api):
    project = data(api.post("/api/projects", {"name": "Keep me"}))
    assert api.delete(f"/api/projects/{project['id']}").status_code == 405


def test_blocker_lifecycle(api):
    blocker = data(api.post("/api/blockers", {
        "description": "Need confirmation on which date column should drive the Account Statement filter.",
        "identified_date": DATE, "dependency": "Business team",
    }))
    assert blocker["status"] == "Open" and blocker["resolved_date"] is None

    day = data(api.get(f"/api/work-logs/{DATE}"))
    assert day["summary"]["blockers"] == 1
    # Still shown on later days while open
    assert data(api.get("/api/work-logs/2026-10-05"))["summary"]["blockers"] == 1
    assert data(api.get("/api/work-logs/2026-10-01"))["summary"]["blockers"] == 0

    resolved = data(api.put(f"/api/blockers/{blocker['id']}", {"status": "Resolved", "resolved_date": "2026-10-04"}))
    assert resolved["resolved_date"] == "2026-10-04" and resolved["resolved_at"]
    assert data(api.get("/api/work-logs/2026-10-06"))["blockers"] == []
    assert len(data(api.get("/api/work-logs/2026-10-04"))["blockers"]) == 1

    reopened = data(api.put(f"/api/blockers/{blocker['id']}", {"status": "Open"}))
    assert reopened["resolved_date"] is None

    assert len(data(api.get("/api/blockers?open=true"))) == 1
    assert api.get("/api/blockers?status=Nope").status_code == 400


def test_blocker_validation(api):
    assert api.post("/api/blockers", {"description": "x", "identified_date": "bad"}).status_code == 400
    assert api.post("/api/blockers", {"description": "", "identified_date": DATE}).status_code == 400
    assert api.post("/api/blockers", {"description": "x", "identified_date": DATE, "status": "Closed"}).status_code == 400


def test_dependencies(api):
    dep = data(api.post("/api/dependencies", {
        "description": "Need stakeholder approval for access governance table design.",
        "type": "Approval", "owner": "Data Governance", "created_date": DATE,
    }))
    assert dep["type"] == "Approval" and dep["status"] == "Open"
    assert data(api.get(f"/api/work-logs/{DATE}"))["summary"]["open_asks"] == 1
    updated = data(api.put(f"/api/dependencies/{dep['id']}", {"status": "Resolved"}))
    assert updated["resolved_at"] is not None
    assert data(api.get("/api/dependencies?type=Approval"))[0]["id"] == dep["id"]
    assert api.post("/api/dependencies", {"description": "x", "type": "Bribe", "created_date": DATE}).status_code == 400
