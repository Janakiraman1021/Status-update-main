from __future__ import annotations

from bson import ObjectId

from .base import UserScopedRepository


class ProjectRepository(UserScopedRepository):
    collection_name = "projects"

    def list(self, user_id: ObjectId, include_archived: bool) -> list[dict]:
        query = {} if include_archived else {"status": "Active"}
        return self.find(user_id, query, sort=[("status", 1), ("name_lower", 1)])

    def by_name(self, user_id: ObjectId, name: str) -> dict | None:
        return self.col.find_one({"user_id": user_id, "name_lower": name.lower()})

    def names_by_id(self, user_id: ObjectId, ids: set[ObjectId]) -> dict[ObjectId, str]:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        return {p["_id"]: p["name"] for p in self.col.find({"user_id": user_id, "_id": {"$in": list(ids)}}, {"name": 1})}

    def ids_matching(self, user_id: ObjectId, pattern: str) -> list[ObjectId]:
        return [p["_id"] for p in self.col.find({"user_id": user_id, "name": {"$regex": pattern, "$options": "i"}}, {"_id": 1})]
