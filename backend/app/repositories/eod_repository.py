"""EOD reports and their immutable versions.

State transitions that must never happen twice (generating, sending, scheduler attempts)
are performed with single atomic find_one_and_update "claims" so concurrent callers
— two scheduler processes, a double-clicked button — cannot both win.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from bson import ObjectId
from pymongo import DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError

from ..constants import EodStatus
from ..utils.datetime_utils import utcnow
from .base import UserScopedRepository

GENERATION_STALE_AFTER = timedelta(minutes=5)


class EodRepository(UserScopedRepository):
    collection_name = "eod_reports"

    def by_date(self, user_id: ObjectId, work_date: str) -> dict | None:
        return self.col.find_one({"user_id": user_id, "work_date": work_date})

    def statuses_between(self, user_id: ObjectId, start: str, end: str) -> dict[str, dict]:
        cursor = self.col.find(
            {"user_id": user_id, "work_date": {"$gte": start, "$lte": end}},
            {"work_date": 1, "status": 1, "sent_version": 1, "current_version": 1},
        )
        return {doc["work_date"]: doc for doc in cursor}

    def recent(self, user_id: ObjectId, limit: int) -> list[dict]:
        return self.find(user_id, {"current_version": {"$gte": 1}}, sort=[("work_date", DESCENDING)], limit=limit)

    # -- claims ------------------------------------------------------------

    def claim_generation(self, user_id: ObjectId, work_date: str, now: datetime) -> dict | None:
        """Move (or create) the day's report into GENERATING. Returns the pre-claim document, or None if busy.

        A report that is SENDING, or GENERATING within the stale window, cannot be claimed.
        """
        stale = now - GENERATION_STALE_AFTER
        query = {
            "user_id": user_id,
            "work_date": work_date,
            "$or": [
                {"status": {"$nin": [EodStatus.GENERATING, EodStatus.SENDING]}},
                {"status": EodStatus.GENERATING, "generating_started_at": {"$lt": stale}},
            ],
        }
        update = {
            "$set": {"status": EodStatus.GENERATING, "generating_started_at": now, "updated_at": now},
            "$setOnInsert": {
                "user_id": user_id, "work_date": work_date, "created_at": now,
                "current_version": 0, "sent_version": None, "auto_attempts": 0,
            },
        }
        try:
            before = self.col.find_one_and_update(query, update, upsert=True, return_document=ReturnDocument.BEFORE)
        except DuplicateKeyError:
            return None  # exists but is busy
        return before or {"status": EodStatus.NOT_GENERATED, "current_version": 0, "_new": True}

    def claim_send(self, user_id: ObjectId, eod_id: ObjectId, allow_resend: bool, now: datetime) -> dict | None:
        allowed = [EodStatus.GENERATED, EodStatus.FAILED] + ([EodStatus.SENT] if allow_resend else [])
        return self.col.find_one_and_update(
            {"_id": eod_id, "user_id": user_id, "current_version": {"$gte": 1}, "status": {"$in": allowed}},
            {"$set": {"status": EodStatus.SENDING, "sending_started_at": now, "updated_at": now}, "$inc": {"send_attempts": 1}},
            return_document=ReturnDocument.BEFORE,
        )

    def claim_auto_attempt(self, user_id: ObjectId, work_date: str, now: datetime, max_attempts: int, retry_after: timedelta) -> dict | None:
        """Reserve one automatic attempt for (user, date). The unique index makes the upsert race-safe."""
        query = {
            "user_id": user_id,
            "work_date": work_date,
            "status": {"$nin": [EodStatus.SENT, EodStatus.SENDING, EodStatus.GENERATING]},
            "auto_attempts": {"$lt": max_attempts},
            "$or": [{"last_auto_attempt_at": None}, {"last_auto_attempt_at": {"$lt": now - retry_after}}],
        }
        update = {
            "$inc": {"auto_attempts": 1},
            "$set": {"last_auto_attempt_at": now, "updated_at": now},
            "$setOnInsert": {
                "user_id": user_id, "work_date": work_date, "created_at": now,
                "status": EodStatus.NOT_GENERATED, "current_version": 0, "sent_version": None,
            },
        }
        try:
            return self.col.find_one_and_update(query, update, upsert=True, return_document=ReturnDocument.AFTER)
        except DuplicateKeyError:
            return None

    def set_state(self, eod_id: ObjectId, fields: dict, unset: tuple[str, ...] = ()) -> dict | None:
        update: dict = {"$set": {**fields, "updated_at": utcnow()}}
        if unset:
            update["$unset"] = {k: "" for k in unset}
        return self.col.find_one_and_update({"_id": eod_id}, update, return_document=ReturnDocument.AFTER)

    def stale_sending(self, older_than: datetime) -> list[dict]:
        return list(self.col.find({"status": EodStatus.SENDING, "sending_started_at": {"$lt": older_than}}))

    def mark_stale_sending_unknown(self, eod_id: ObjectId, older_than: datetime, fields: dict) -> bool:
        result = self.col.update_one(
            {"_id": eod_id, "status": EodStatus.SENDING, "sending_started_at": {"$lt": older_than}},
            {"$set": {**fields, "updated_at": utcnow()}},
        )
        return result.modified_count == 1


class EodVersionRepository(UserScopedRepository):
    collection_name = "eod_versions"

    def for_report(self, user_id: ObjectId, eod_id: ObjectId) -> list[dict]:
        return self.find(user_id, {"eod_id": eod_id}, sort=[("version", DESCENDING)])

    def current(self, user_id: ObjectId, eod_id: ObjectId) -> dict | None:
        return self.col.find_one({"user_id": user_id, "eod_id": eod_id, "is_current": True})

    def by_number(self, user_id: ObjectId, eod_id: ObjectId, version: int) -> dict | None:
        return self.col.find_one({"user_id": user_id, "eod_id": eod_id, "version": version})

    def add(self, user_id: ObjectId, eod_id: ObjectId, work_date: str, version: int, fields: dict) -> dict:
        self.col.update_many({"user_id": user_id, "eod_id": eod_id, "is_current": True}, {"$set": {"is_current": False}})
        return self.insert(user_id, {"eod_id": eod_id, "work_date": work_date, "version": version, "is_current": True, "sent_at": None, **fields})
