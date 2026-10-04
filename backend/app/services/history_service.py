"""Work and EOD history with server-side filtering, search and pagination."""
from __future__ import annotations

import re
from datetime import date

from bson import ObjectId

from ..repositories import Repositories
from ..utils.datetime_utils import format_time
from ..utils.errors import ValidationFailed
from .ai_service import AIError, AIProvider
from .settings_service import SettingsService
from .work_log_service import WorkLogService

MAX_SUMMARY_DAYS = 31


def _date_range(date_from: str | None, date_to: str | None, field: str) -> dict:
    query: dict = {}
    if date_from:
        query["$gte"] = date_from
    if date_to:
        query["$lte"] = date_to
    if date_from and date_to and date_from > date_to:
        raise ValidationFailed("The start date must be before the end date.")
    return {field: query} if query else {}


class HistoryService:
    def __init__(self, repos: Repositories, settings: SettingsService, work_logs: WorkLogService, ai: AIProvider):
        self.repos = repos
        self.settings = settings
        self.work_logs = work_logs
        self.ai = ai

    def work(self, user_id: ObjectId, *, page: int, limit: int, date_from=None, date_to=None, project_id=None,
             category=None, status=None, q: str | None = None) -> tuple[list[dict], int]:
        query: dict = _date_range(date_from, date_to, "work_date")
        if project_id:
            query["project_id"] = ObjectId(project_id)
        if category:
            query["category"] = category
        if status:
            query["status"] = status
        if q:
            pattern = re.escape(q.strip())
            matching_projects = self.repos.projects.ids_matching(user_id, pattern)
            query["$or"] = [{"description": {"$regex": pattern, "$options": "i"}}]
            if matching_projects:
                query["$or"].append({"project_id": {"$in": matching_projects}})
        items, total = self.repos.work_items.paginate(user_id, query, [("work_date", -1), ("timestamp", -1)], page, limit)
        return self.work_logs.decorate_items(user_id, items, self.settings.timezone(user_id)), total

    def eods(self, user_id: ObjectId, *, page: int, limit: int, date_from=None, date_to=None, status=None, q=None) -> tuple[list[dict], int]:
        query: dict = {"current_version": {"$gte": 1}, **_date_range(date_from, date_to, "work_date")}
        if status:
            query["status"] = status
        if q:
            pattern = re.escape(q.strip())
            query["$or"] = [{"subject": {"$regex": pattern, "$options": "i"}}, {"project_label": {"$regex": pattern, "$options": "i"}},
                            {"body": {"$regex": pattern, "$options": "i"}}]
        docs, total = self.repos.eods.paginate(user_id, query, [("work_date", -1)], page, limit)
        tz = self.settings.timezone(user_id)
        rows = [
            {"id": d["_id"], "work_date": d["work_date"], "status": d["status"], "subject": d.get("subject"),
             "project_label": d.get("project_label"), "current_version": d.get("current_version"),
             "sent_version": d.get("sent_version"), "generated_at": d.get("generated_at"), "sent_at": d.get("sent_at"),
             "generated_time_label": format_time(d["generated_at"], tz) if d.get("generated_at") else None,
             "sent_time_label": format_time(d["sent_at"], tz) if d.get("sent_at") else None,
             "last_error": d.get("last_error")}
            for d in docs
        ]
        return rows, total

    def search(self, user_id: ObjectId, q: str, limit: int = 10) -> dict:
        """Search beyond work entries: notes / next steps, blockers and dependencies."""
        q = (q or "").strip()
        if len(q) < 2:
            raise ValidationFailed("Search text must be at least 2 characters.")
        regex = {"$regex": re.escape(q), "$options": "i"}
        logs = self.repos.work_logs.find(
            user_id, {"$or": [{"quick_notes": regex}, {"next_steps": regex}, {"learnings": regex}, {"meetings": regex}, {"metrics": regex}]},
            sort=[("work_date", -1)], limit=limit,
        )
        blockers = self.repos.blockers.find(user_id, {"$or": [{"description": regex}, {"dependency": regex}]}, sort=[("identified_date", -1)], limit=limit)
        deps = self.repos.dependencies.find(user_id, {"$or": [{"description": regex}, {"owner": regex}]}, sort=[("created_date", -1)], limit=limit)
        projects = self.repos.projects.find(user_id, {"$or": [{"name": regex}, {"description": regex}]}, limit=limit)

        def snippet(text: str | None) -> str | None:
            if not text:
                return None
            idx = text.lower().find(q.lower())
            if idx < 0:
                return None
            start = max(0, idx - 60)
            return ("…" if start else "") + text[start: idx + len(q) + 60].replace("\n", " ") + ("…" if idx + len(q) + 60 < len(text) else "")

        return {
            "notes": [
                {"work_date": l["work_date"], "field": field, "snippet": snippet(l.get(field))}
                for l in logs for field in ("quick_notes", "next_steps", "learnings", "meetings", "metrics") if snippet(l.get(field))
            ],
            "blockers": [{"id": b["_id"], "description": b["description"], "status": b["status"], "identified_date": b["identified_date"]} for b in blockers],
            "dependencies": [{"id": d["_id"], "description": d["description"], "status": d["status"], "type": d["type"], "created_date": d["created_date"]} for d in deps],
            "projects": [{"id": p["_id"], "name": p["name"], "status": p["status"]} for p in projects],
        }

    def summarize(self, user_id: ObjectId, date_from: str, date_to: str) -> dict:
        if not date_from or not date_to:
            raise ValidationFailed("Both start and end dates are required.")
        days = (date.fromisoformat(date_to) - date.fromisoformat(date_from)).days
        if days < 0:
            raise ValidationFailed("The start date must be before the end date.")
        if days >= MAX_SUMMARY_DAYS:
            raise ValidationFailed(f"Summaries are limited to {MAX_SUMMARY_DAYS} days.")
        items = self.work_logs.decorate_items(
            user_id, self.repos.work_items.find(user_id, {"work_date": {"$gte": date_from, "$lte": date_to}}, sort=[("work_date", 1), ("timestamp", 1)], limit=2000),
            self.settings.timezone(user_id),
        )
        logs = self.repos.work_logs.find(user_id, {"work_date": {"$gte": date_from, "$lte": date_to}}, sort=[("work_date", 1)])
        lines: list[str] = []
        for log in logs:
            if log.get("quick_notes"):
                lines.append(f"[{log['work_date']}] Notes: {log['quick_notes']}")
            if log.get("next_steps"):
                lines.append(f"[{log['work_date']}] Next steps: {log['next_steps']}")
        for item in items:
            meta = ", ".join(x for x in (item.get("project_name"), item.get("category"), item.get("status")) if x)
            lines.append(f"[{item['work_date']}] {item['description']}" + (f" ({meta})" if meta else ""))
        if not lines:
            return {"summary": "", "entry_count": 0}
        try:
            summary = self.ai.summarize("\n".join(lines))
        except AIError as exc:
            raise ValidationFailed(str(exc), code="AI_SUMMARY_FAILED", status_code=502) from exc
        return {"summary": summary, "entry_count": len(items), "provider": self.ai.name}
