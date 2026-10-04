"""Base repository: every query is scoped to the owning user."""
from __future__ import annotations

from typing import Any, Iterable

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database

from ..utils.datetime_utils import utcnow


class UserScopedRepository:
    collection_name: str = ""

    def __init__(self, db: Database):
        self.db = db
        self.col: Collection = db[self.collection_name]

    def get(self, user_id: ObjectId, doc_id: ObjectId) -> dict | None:
        return self.col.find_one({"_id": doc_id, "user_id": user_id})

    def insert(self, user_id: ObjectId, doc: dict) -> dict:
        now = utcnow()
        doc = {**doc, "user_id": user_id, "created_at": now, "updated_at": now}
        result = self.col.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def update(self, user_id: ObjectId, doc_id: ObjectId, fields: dict, unset: Iterable[str] = ()) -> dict | None:
        update: dict[str, Any] = {"$set": {**fields, "updated_at": utcnow()}}
        if unset:
            update["$unset"] = {name: "" for name in unset}
        return self.col.find_one_and_update(
            {"_id": doc_id, "user_id": user_id}, update, return_document=ReturnDocument.AFTER
        )

    def delete(self, user_id: ObjectId, doc_id: ObjectId) -> bool:
        return self.col.delete_one({"_id": doc_id, "user_id": user_id}).deleted_count == 1

    def find(self, user_id: ObjectId, query: dict | None = None, sort: list | None = None, skip: int = 0, limit: int = 0) -> list[dict]:
        cursor = self.col.find({**(query or {}), "user_id": user_id})
        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)

    def count(self, user_id: ObjectId, query: dict | None = None) -> int:
        return self.col.count_documents({**(query or {}), "user_id": user_id})

    def paginate(self, user_id: ObjectId, query: dict, sort: list, page: int, limit: int) -> tuple[list[dict], int]:
        total = self.count(user_id, query)
        items = self.find(user_id, query, sort=sort, skip=(page - 1) * limit, limit=limit)
        return items, total
