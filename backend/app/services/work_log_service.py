"""Daily work logs (free-form sections) and timestamped work entries."""
from __future__ import annotations

import logging

from bson import ObjectId

from ..constants import EodStatus
from ..repositories import Repositories
from ..utils.datetime_utils import (
    default_entry_timestamp, format_long, format_time, get_zone, local_datetime, parse_date, to_utc,
)
from ..utils.errors import NotFound
from .project_service import ProjectService
from .settings_service import SettingsService

logger = logging.getLogger(__name__)

LOG_FIELDS = ("project_id", "quick_notes", "next_steps", "learnings", "meetings", "metrics")


class WorkLogService:
    def __init__(self, repos: Repositories, projects: ProjectService, settings: SettingsService):
        self.repos = repos
        self.projects = projects
        self.settings = settings

    # -- read ---------------------------------------------------------------

    def has_work(self, user_id: ObjectId, work_date: str) -> bool:
        return self.repos.work_items.count(user_id, {"work_date": work_date}) > 0 or self.repos.work_logs.has_content(user_id, work_date)

    def decorate_items(self, user_id: ObjectId, items: list[dict], tz: str) -> list[dict]:
        names = self.repos.projects.names_by_id(user_id, {i.get("project_id") for i in items})
        for item in items:
            item["project_name"] = names.get(item.get("project_id"))
            item["time_label"] = format_time(item["timestamp"], tz)
            item["time"] = to_utc(item["timestamp"]).astimezone(get_zone(tz)).strftime("%H:%M")
        return items

    def day(self, user_id: ObjectId, work_date: str) -> dict:
        parse_date(work_date)
        settings = self.settings.get(user_id)
        tz = settings["timezone"]
        log = self.repos.work_logs.by_date(user_id, work_date)
        items = self.decorate_items(user_id, self.repos.work_items.for_date(user_id, work_date), tz)
        blockers = self.repos.blockers.relevant_for_date(user_id, work_date)
        dependencies = self.repos.dependencies.relevant_for_date(user_id, work_date)
        eod = self.repos.eods.by_date(user_id, work_date)

        project_id = (log or {}).get("project_id") or (None if log else settings.get("default_project_id"))
        project_names = self.repos.projects.names_by_id(
            user_id, {project_id} | {b.get("project_id") for b in blockers} | {d.get("project_id") for d in dependencies}
        )
        for doc in (*blockers, *dependencies):
            doc["project_name"] = project_names.get(doc.get("project_id"))

        counts: dict[str, int] = {}
        for item in items:
            counts[item.get("status") or "Uncategorized"] = counts.get(item.get("status") or "Uncategorized", 0) + 1
        open_blockers = [b for b in blockers if b["status"] != "Resolved"]

        return {
            "work_date": work_date,
            "date_label": format_long(work_date),
            "log": log,
            "project_id": project_id,
            "project_name": project_names.get(project_id),
            "entries": items,
            "blockers": blockers,
            "dependencies": dependencies,
            "summary": {
                "completed": counts.get("Completed", 0),
                "in_progress": counts.get("In Progress", 0),
                "blocked": counts.get("Blocked", 0),
                "planned": counts.get("Planned", 0),
                "blockers": len(open_blockers),
                "open_asks": len([d for d in dependencies if d["status"] != "Resolved"]),
                "total_entries": len(items),
            },
            "eod": {
                "id": eod["_id"] if eod else None,
                "status": eod["status"] if eod else EodStatus.NOT_GENERATED,
                "sent_at": eod.get("sent_at") if eod else None,
                "current_version": eod.get("current_version", 0) if eod else 0,
            },
            "has_work": bool(items) or bool((log or {}).get("quick_notes")),
        }

    # -- work log -----------------------------------------------------------

    def _log_fields(self, user_id: ObjectId, data: dict) -> dict:
        fields = {k: data[k] for k in LOG_FIELDS if k in data}
        if "project_id" in fields:
            fields["project_id"] = self.projects.require_usable(user_id, fields["project_id"], allow_archived=True)
        return fields

    def upsert(self, user_id: ObjectId, work_date: str, data: dict) -> dict:
        fields = self._log_fields(user_id, data)
        if "project_id" not in fields and not self.repos.work_logs.by_date(user_id, work_date):
            # A new day starts on the user's default project unless one was chosen explicitly.
            default = self.settings.get(user_id).get("default_project_id")
            project = self.repos.projects.get(user_id, default) if default else None
            if project and project["status"] == "Active":
                fields["project_id"] = project["_id"]
        log = self.repos.work_logs.upsert(user_id, work_date, fields)
        logger.info("Work log saved", extra={"user_id": str(user_id), "work_date": work_date})
        return log

    def update(self, user_id: ObjectId, log_id: ObjectId, data: dict) -> dict:
        if not self.repos.work_logs.get(user_id, log_id):
            raise NotFound("Work log not found.", code="WORK_LOG_NOT_FOUND")
        return self.repos.work_logs.update(user_id, log_id, self._log_fields(user_id, data))

    def delete(self, user_id: ObjectId, log_id: ObjectId) -> None:
        """Clears the day's notes. Entries are removed individually, so nothing else is lost."""
        if not self.repos.work_logs.delete(user_id, log_id):
            raise NotFound("Work log not found.", code="WORK_LOG_NOT_FOUND")

    # -- entries ------------------------------------------------------------

    def _timestamp(self, work_date: str, hhmm: str | None, tz: str):
        if hhmm:
            return to_utc(local_datetime(work_date, hhmm, tz))
        return default_entry_timestamp(work_date, tz)

    def create_item(self, user_id: ObjectId, data: dict) -> dict:
        tz = self.settings.timezone(user_id)
        work_date = data["work_date"]
        log = self.repos.work_logs.by_date(user_id, work_date)
        project_id = data.get("project_id")
        if project_id is None and log and log.get("project_id"):
            project_id = log["project_id"]
        item = self.repos.work_items.insert(user_id, {
            "work_date": work_date,
            "description": data["description"],
            "project_id": self.projects.require_usable(user_id, project_id),
            "category": data.get("category"),
            "status": data.get("status"),
            "timestamp": self._timestamp(work_date, data.get("time"), tz),
        })
        return self.decorate_items(user_id, [item], tz)[0]

    def create_items(self, user_id: ObjectId, work_date: str, items: list[dict]) -> list[dict]:
        return [self.create_item(user_id, {**item, "work_date": work_date}) for item in items]

    def update_item(self, user_id: ObjectId, item_id: ObjectId, data: dict) -> dict:
        item = self.repos.work_items.get(user_id, item_id)
        if not item:
            raise NotFound("Work entry not found.", code="WORK_ITEM_NOT_FOUND")
        tz = self.settings.timezone(user_id)
        fields = {k: data[k] for k in ("description", "category", "status") if k in data}
        if fields.get("description") is None:
            fields.pop("description", None)
        if "project_id" in data:
            fields["project_id"] = self.projects.require_usable(user_id, data["project_id"], allow_archived=True)
        if data.get("time"):
            fields["timestamp"] = self._timestamp(item["work_date"], data["time"], tz)
        updated = self.repos.work_items.update(user_id, item_id, fields)
        return self.decorate_items(user_id, [updated], tz)[0]

    def delete_item(self, user_id: ObjectId, item_id: ObjectId) -> None:
        if not self.repos.work_items.delete(user_id, item_id):
            raise NotFound("Work entry not found.", code="WORK_ITEM_NOT_FOUND")

    def last_change(self, user_id: ObjectId, work_date: str):
        """Most recent modification to the day's inputs (used to flag outdated EODs)."""
        stamps = []
        log = self.repos.work_logs.by_date(user_id, work_date)
        if log:
            stamps.append(log["updated_at"])
        latest = self.repos.work_items.find(user_id, {"work_date": work_date}, sort=[("updated_at", -1)], limit=1)
        if latest:
            stamps.append(latest[0]["updated_at"])
        return max((to_utc(s) for s in stamps), default=None)
