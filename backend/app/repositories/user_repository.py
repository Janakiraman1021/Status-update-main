from __future__ import annotations

from datetime import datetime

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database

from ..utils.datetime_utils import utcnow


class UserRepository:
    def __init__(self, db: Database):
        self.col = db.users

    def by_email(self, email: str) -> dict | None:
        return self.col.find_one({"email": email.strip().lower()})

    def by_id(self, user_id: ObjectId) -> dict | None:
        return self.col.find_one({"_id": user_id, "is_active": {"$ne": False}})

    def create(self, name: str, email: str, password_hash: str) -> dict:
        now = utcnow()
        doc = {
            "name": name.strip(),
            "email": email.strip().lower(),
            "password_hash": password_hash,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        doc["_id"] = self.col.insert_one(doc).inserted_id
        return doc

    def update(self, user_id: ObjectId, fields: dict) -> dict | None:
        return self.col.find_one_and_update(
            {"_id": user_id}, {"$set": {**fields, "updated_at": utcnow()}}, return_document=ReturnDocument.AFTER
        )

    def touch_login(self, user_id: ObjectId, when: datetime) -> None:
        self.col.update_one({"_id": user_id}, {"$set": {"last_login_at": when}})

    def all_active_ids(self) -> list[ObjectId]:
        return [doc["_id"] for doc in self.col.find({"is_active": {"$ne": False}}, {"_id": 1})]


class SessionRepository:
    def __init__(self, db: Database):
        self.col = db.sessions

    def create(self, user_id: ObjectId, token_hash: str, csrf_token: str, expires_at: datetime, remember: bool, user_agent: str | None) -> dict:
        doc = {
            "user_id": user_id,
            "token_hash": token_hash,
            "csrf_token": csrf_token,
            "remember": remember,
            "expires_at": expires_at,
            "created_at": utcnow(),
            "user_agent": (user_agent or "")[:300],
        }
        doc["_id"] = self.col.insert_one(doc).inserted_id
        return doc

    def active(self, token_hash: str) -> dict | None:
        return self.col.find_one({"token_hash": token_hash, "expires_at": {"$gt": utcnow()}})

    def delete(self, token_hash: str) -> None:
        self.col.delete_one({"token_hash": token_hash})
