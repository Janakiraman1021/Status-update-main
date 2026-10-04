from __future__ import annotations

from bson import ObjectId
from pymongo import ReturnDocument

from ..utils.datetime_utils import utcnow
from .base import UserScopedRepository


class WorkLogRepository(UserScopedRepository):
    """One document per user per local work date holding the day's free-form sections."""

    collection_name = "work_logs"

    def by_date(self, user_id: ObjectId, work_date: str) -> dict | None:
        return self.col.find_one({"user_id": user_id, "work_date": work_date})

    def upsert(self, user_id: ObjectId, work_date: str, fields: dict) -> dict:
        now = utcnow()
        return self.col.find_one_and_update(
            {"user_id": user_id, "work_date": work_date},
            {"$set": {**fields, "updated_at": now}, "$setOnInsert": {"user_id": user_id, "work_date": work_date, "created_at": now}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    def dates_with_content(self, user_id: ObjectId, start: str, end: str) -> set[str]:
        cursor = self.col.find(
            {"user_id": user_id, "work_date": {"$gte": start, "$lte": end}, "quick_notes": {"$nin": [None, ""]}},
            {"work_date": 1},
        )
        return {doc["work_date"] for doc in cursor}

    def has_content(self, user_id: ObjectId, work_date: str) -> bool:
        return self.col.count_documents({"user_id": user_id, "work_date": work_date, "quick_notes": {"$nin": [None, ""]}}, limit=1) > 0


class WorkItemRepository(UserScopedRepository):
    collection_name = "work_items"

    def for_date(self, user_id: ObjectId, work_date: str) -> list[dict]:
        return self.find(user_id, {"work_date": work_date}, sort=[("timestamp", 1), ("_id", 1)])

    def dates_with_items(self, user_id: ObjectId, start: str, end: str) -> set[str]:
        return set(self.col.distinct("work_date", {"user_id": user_id, "work_date": {"$gte": start, "$lte": end}}))

    def status_counts(self, user_id: ObjectId, work_date: str) -> dict[str, int]:
        pipeline = [
            {"$match": {"user_id": user_id, "work_date": work_date}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        return {(row["_id"] or "Uncategorized"): row["count"] for row in self.col.aggregate(pipeline)}

    def recent(self, user_id: ObjectId, limit: int) -> list[dict]:
        return self.find(user_id, sort=[("updated_at", -1)], limit=limit)

    def count_for_project(self, user_id: ObjectId, project_id: ObjectId) -> int:
        return self.count(user_id, {"project_id": project_id})
