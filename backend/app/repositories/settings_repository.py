from __future__ import annotations

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database

from ..utils.datetime_utils import utcnow


class SettingsRepository:
    def __init__(self, db: Database):
        self.col = db.settings

    def get(self, user_id: ObjectId) -> dict | None:
        return self.col.find_one({"user_id": user_id})

    def upsert(self, user_id: ObjectId, fields: dict, defaults: dict) -> dict:
        now = utcnow()
        on_insert = {k: v for k, v in defaults.items() if k not in fields}
        return self.col.find_one_and_update(
            {"user_id": user_id},
            {"$set": {**fields, "updated_at": now}, "$setOnInsert": {**on_insert, "user_id": user_id, "created_at": now}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    def automation_candidates(self) -> list[dict]:
        return list(self.col.find({"$or": [{"auto_eod_enabled": True}, {"reminder_enabled": True}]}))


class JobLockRepository:
    """Insert-once locks backed by a unique index. Used to make scheduled side effects idempotent."""

    def __init__(self, db: Database):
        self.col = db.job_locks

    def acquire(self, key: str, expires_at, meta: dict | None = None) -> bool:
        from pymongo.errors import DuplicateKeyError

        try:
            self.col.insert_one({"key": key, "created_at": utcnow(), "expires_at": expires_at, **(meta or {})})
            return True
        except DuplicateKeyError:
            return False

    def release(self, key: str) -> None:
        self.col.delete_one({"key": key})
