"""Blockers and dependencies / asks."""
from __future__ import annotations

from bson import ObjectId

from ..repositories import Repositories
from ..utils.datetime_utils import local_today, utcnow
from ..utils.errors import NotFound
from .project_service import ProjectService
from .settings_service import SettingsService


class TrackingService:
    def __init__(self, repos: Repositories, projects: ProjectService, settings: SettingsService):
        self.repos = repos
        self.projects = projects
        self.settings = settings

    def _with_project_names(self, user_id: ObjectId, docs: list[dict]) -> list[dict]:
        names = self.repos.projects.names_by_id(user_id, {d.get("project_id") for d in docs})
        for doc in docs:
            doc["project_name"] = names.get(doc.get("project_id"))
        return docs

    def _resolution_fields(self, user_id: ObjectId, status: str | None, current: dict | None, explicit_date: str | None = None) -> dict:
        if status == "Resolved" and (not current or current.get("status") != "Resolved"):
            return {"resolved_date": explicit_date or local_today(self.settings.timezone(user_id)), "resolved_at": utcnow()}
        if status and status != "Resolved" and current and current.get("status") == "Resolved":
            return {"resolved_date": None, "resolved_at": None}
        return {}

    # -- blockers -----------------------------------------------------------

    def list_blockers(self, user_id: ObjectId, status: str | None = None, open_only: bool = False) -> list[dict]:
        query: dict = {}
        if status:
            query["status"] = status
        elif open_only:
            query["status"] = {"$ne": "Resolved"}
        return self._with_project_names(user_id, self.repos.blockers.find(user_id, query, sort=[("identified_date", -1), ("_id", -1)], limit=500))

    def create_blocker(self, user_id: ObjectId, data: dict) -> dict:
        doc = {
            "description": data["description"],
            "project_id": self.projects.require_usable(user_id, data.get("project_id")),
            "identified_date": data["identified_date"],
            "status": data.get("status", "Open"),
            "dependency": data.get("dependency"),
            "expected_resolution": data.get("expected_resolution"),
            "resolved_date": None,
            "resolved_at": None,
        }
        doc.update(self._resolution_fields(user_id, doc["status"], None))
        return self._with_project_names(user_id, [self.repos.blockers.insert(user_id, doc)])[0]

    def update_blocker(self, user_id: ObjectId, blocker_id: ObjectId, data: dict) -> dict:
        current = self.repos.blockers.get(user_id, blocker_id)
        if not current:
            raise NotFound("Blocker not found.", code="BLOCKER_NOT_FOUND")
        fields = {k: data[k] for k in ("description", "status", "dependency", "expected_resolution") if k in data}
        if fields.get("description") is None:
            fields.pop("description", None)
        if fields.get("status") is None:
            fields.pop("status", None)
        if "project_id" in data:
            fields["project_id"] = self.projects.require_usable(user_id, data["project_id"], allow_archived=True)
        fields.update(self._resolution_fields(user_id, fields.get("status"), current, data.get("resolved_date")))
        return self._with_project_names(user_id, [self.repos.blockers.update(user_id, blocker_id, fields)])[0]

    # -- dependencies -------------------------------------------------------

    def list_dependencies(self, user_id: ObjectId, status: str | None = None, type_: str | None = None, open_only: bool = False) -> list[dict]:
        query: dict = {}
        if status:
            query["status"] = status
        elif open_only:
            query["status"] = {"$ne": "Resolved"}
        if type_:
            query["type"] = type_
        return self._with_project_names(user_id, self.repos.dependencies.find(user_id, query, sort=[("created_date", -1), ("_id", -1)], limit=500))

    def create_dependency(self, user_id: ObjectId, data: dict) -> dict:
        doc = {
            "description": data["description"],
            "type": data.get("type", "Dependency"),
            "owner": data.get("owner"),
            "status": data.get("status", "Open"),
            "project_id": self.projects.require_usable(user_id, data.get("project_id")),
            "created_date": data["created_date"],
            "resolved_date": None,
            "resolved_at": None,
        }
        doc.update(self._resolution_fields(user_id, doc["status"], None))
        return self._with_project_names(user_id, [self.repos.dependencies.insert(user_id, doc)])[0]

    def update_dependency(self, user_id: ObjectId, dep_id: ObjectId, data: dict) -> dict:
        current = self.repos.dependencies.get(user_id, dep_id)
        if not current:
            raise NotFound("Dependency not found.", code="DEPENDENCY_NOT_FOUND")
        fields = {k: data[k] for k in ("description", "type", "owner", "status") if k in data}
        for key in ("description", "type", "status"):
            if fields.get(key) is None:
                fields.pop(key, None)
        if "project_id" in data:
            fields["project_id"] = self.projects.require_usable(user_id, data["project_id"], allow_archived=True)
        fields.update(self._resolution_fields(user_id, fields.get("status"), current))
        return self._with_project_names(user_id, [self.repos.dependencies.update(user_id, dep_id, fields)])[0]
