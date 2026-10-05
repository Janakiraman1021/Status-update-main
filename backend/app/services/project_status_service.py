from __future__ import annotations

from bson import ObjectId

from ..repositories import Repositories
from ..utils.datetime_utils import parse_date
from ..utils.errors import ValidationFailed
from .project_service import ProjectService


class ProjectStatusService:
    def __init__(self, repos: Repositories, projects: ProjectService):
        self.repos = repos
        self.projects = projects

    def get(self, user_id: ObjectId, project_id: ObjectId, work_date: str) -> dict | None:
        parse_date(work_date, "work_date")
        self.projects.get(user_id, project_id)
        return self.repos.project_statuses.by_project_date(user_id, project_id, work_date)

    def list(self, user_id: ObjectId, project_id: ObjectId) -> list[dict]:
        self.projects.get(user_id, project_id)
        return self.repos.project_statuses.for_project(user_id, project_id)

    def save(self, user_id: ObjectId, data: dict) -> dict:
        project_id = self.projects.require_usable(user_id, data["project_id"], allow_archived=True)
        work_date = data["work_date"]
        parse_date(work_date, "work_date")
        if not data.get("daily_update", "").strip():
            raise ValidationFailed("Add a short update before saving.", details={"daily_update": "This field cannot be empty"})
        fields = {
            "status": data.get("status", "On track"),
            "daily_update": data["daily_update"],
            "next_step": data.get("next_step"),
            "help_needed": data.get("help_needed"),
        }
        return self.repos.project_statuses.upsert_for_date(user_id, project_id, work_date, fields)
