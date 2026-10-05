from __future__ import annotations

from bson import ObjectId

from ..utils.datetime_utils import utcnow
from .base import UserScopedRepository


class ProjectStatusRepository(UserScopedRepository):
    collection_name = "project_statuses"

    def by_project_date(self, user_id: ObjectId, project_id: ObjectId, work_date: str) -> dict | None:
        return self.col.find_one({"user_id": user_id, "project_id": project_id, "work_date": work_date})

    def for_project(self, user_id: ObjectId, project_id: ObjectId, limit: int = 30) -> list[dict]:
        return self.find(user_id, {"project_id": project_id}, sort=[("work_date", -1)], limit=limit)

    def upsert_for_date(self, user_id: ObjectId, project_id: ObjectId, work_date: str, fields: dict) -> dict:
        now = utcnow()
        self.col.update_one(
            {"user_id": user_id, "project_id": project_id, "work_date": work_date},
            {
                "$set": {**fields, "updated_at": now},
                "$setOnInsert": {
                    "user_id": user_id,
                    "project_id": project_id,
                    "work_date": work_date,
                    "created_at": now,
                },
            },
            upsert=True,
        )
        status = self.by_project_date(user_id, project_id, work_date)
        if status is None:
            raise RuntimeError("Project status was not available after saving.")
        return status
