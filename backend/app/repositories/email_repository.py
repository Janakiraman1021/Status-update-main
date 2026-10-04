from __future__ import annotations

from bson import ObjectId
from pymongo.database import Database

from ..utils.datetime_utils import utcnow


class EmailLogRepository:
    def __init__(self, db: Database):
        self.col = db.email_logs

    def record(self, user_id: ObjectId | None, kind: str, to: list[str], cc: list[str], bcc: list[str], subject: str,
               provider: str, success: bool, message_id: str | None = None, error: str | None = None,
               reference: dict | None = None) -> dict:
        doc = {
            "user_id": user_id,
            "kind": kind,
            "to": to,
            "cc": cc,
            "bcc": bcc,
            "subject": subject,
            "provider": provider,
            "success": success,
            "message_id": message_id,
            "error": error,
            "reference": reference or {},
            "created_at": utcnow(),
        }
        doc["_id"] = self.col.insert_one(doc).inserted_id
        return doc

    def recent(self, user_id: ObjectId, limit: int = 20) -> list[dict]:
        return list(self.col.find({"user_id": user_id}).sort("created_at", -1).limit(limit))

    def for_reference(self, user_id: ObjectId, key: str, value) -> list[dict]:
        return list(self.col.find({"user_id": user_id, f"reference.{key}": value}).sort("created_at", -1))
