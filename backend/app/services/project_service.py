from __future__ import annotations

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from ..repositories import Repositories
from ..utils.datetime_utils import utcnow
from ..utils.errors import Conflict, NotFound, ValidationFailed


class ProjectService:
    def __init__(self, repos: Repositories):
        self.repos = repos

    def list(self, user_id: ObjectId, include_archived: bool = False) -> list[dict]:
        projects = self.repos.projects.list(user_id, include_archived)
        counts = {
            row["_id"]: row["count"]
            for row in self.repos.work_items.col.aggregate([
                {"$match": {"user_id": user_id, "project_id": {"$in": [p["_id"] for p in projects]}}},
                {"$group": {"_id": "$project_id", "count": {"$sum": 1}}},
            ])
        } if projects else {}
        for project in projects:
            project["entry_count"] = counts.get(project["_id"], 0)
        return projects

    def get(self, user_id: ObjectId, project_id: ObjectId) -> dict:
        project = self.repos.projects.get(user_id, project_id)
        if not project:
            raise NotFound("Project not found.", code="PROJECT_NOT_FOUND")
        return project

    def require_usable(self, user_id: ObjectId, project_id: str | ObjectId | None, allow_archived: bool = False) -> ObjectId | None:
        """Validate that a project referenced by the client belongs to the user."""
        if not project_id:
            return None
        project = self.repos.projects.get(user_id, ObjectId(project_id))
        if not project:
            raise ValidationFailed("Project not found.", details={"project_id": "Unknown project"})
        if project["status"] == "Archived" and not allow_archived:
            raise ValidationFailed("This project is archived.", details={"project_id": "Project is archived"})
        return project["_id"]

    def create(self, user_id: ObjectId, name: str, description: str | None) -> dict:
        try:
            return self.repos.projects.insert(user_id, {
                "name": name, "name_lower": name.lower(), "description": description,
                "status": "Active", "archived_at": None,
            })
        except DuplicateKeyError as exc:
            raise Conflict("A project with this name already exists.", code="PROJECT_EXISTS") from exc

    def update(self, user_id: ObjectId, project_id: ObjectId, data: dict) -> dict:
        self.get(user_id, project_id)
        fields: dict = {}
        if data.get("name"):
            fields["name"] = data["name"]
            fields["name_lower"] = data["name"].lower()
        if "description" in data:
            fields["description"] = data["description"]
        if data.get("status") == "Archived":
            fields.update(status="Archived", archived_at=utcnow())
        elif data.get("status") == "Active":
            fields.update(status="Active", archived_at=None)
        try:
            return self.repos.projects.update(user_id, project_id, fields)
        except DuplicateKeyError as exc:
            raise Conflict("A project with this name already exists.", code="PROJECT_EXISTS") from exc

    def archive(self, user_id: ObjectId, project_id: ObjectId) -> dict:
        project = self.get(user_id, project_id)
        if project["status"] == "Archived":
            return project
        return self.repos.projects.update(user_id, project_id, {"status": "Archived", "archived_at": utcnow()})
