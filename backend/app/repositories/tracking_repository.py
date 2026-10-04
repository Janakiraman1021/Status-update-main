"""Blockers and dependencies/asks."""
from __future__ import annotations

from bson import ObjectId

from .base import UserScopedRepository


class BlockerRepository(UserScopedRepository):
    collection_name = "blockers"

    def relevant_for_date(self, user_id: ObjectId, work_date: str) -> list[dict]:
        """Blockers identified on or before the date that were unresolved on that date."""
        query = {
            "identified_date": {"$lte": work_date},
            "$or": [{"status": {"$ne": "Resolved"}}, {"resolved_date": {"$gte": work_date}}],
        }
        return self.find(user_id, query, sort=[("identified_date", -1), ("_id", -1)])

    def open_count(self, user_id: ObjectId) -> int:
        return self.count(user_id, {"status": {"$ne": "Resolved"}})


class DependencyRepository(UserScopedRepository):
    collection_name = "dependencies"

    def relevant_for_date(self, user_id: ObjectId, work_date: str) -> list[dict]:
        query = {
            "created_date": {"$lte": work_date},
            "$or": [{"status": {"$ne": "Resolved"}}, {"resolved_date": {"$gte": work_date}}],
        }
        return self.find(user_id, query, sort=[("created_date", -1), ("_id", -1)])

    def open_count(self, user_id: ObjectId) -> int:
        return self.count(user_id, {"status": {"$ne": "Resolved"}})
