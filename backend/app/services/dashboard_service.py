"""Dashboard and calendar read models."""
from __future__ import annotations

from datetime import date, timedelta

from bson import ObjectId

from ..constants import EodStatus
from ..repositories import Repositories
from ..utils.datetime_utils import format_long, format_time, local_now, month_bounds
from .settings_service import SettingsService
from .work_log_service import WorkLogService


def greeting(hour: int) -> str:
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


class DashboardService:
    def __init__(self, repos: Repositories, settings: SettingsService, work_logs: WorkLogService):
        self.repos = repos
        self.settings = settings
        self.work_logs = work_logs

    def dashboard(self, user: dict) -> dict:
        user_id = user["_id"]
        settings = self.settings.get(user_id)
        tz = settings["timezone"]
        now_local = local_now(tz)
        today = now_local.date().isoformat()
        day = self.work_logs.day(user_id, today)

        recent_items = self.work_logs.decorate_items(user_id, self.repos.work_items.recent(user_id, 8), tz)
        recent_eods = self.repos.eods.recent(user_id, 5)

        week_start = now_local.date() - timedelta(days=now_local.weekday())
        logged = self.repos.work_items.dates_with_items(user_id, week_start.isoformat(), today) | \
            self.repos.work_logs.dates_with_content(user_id, week_start.isoformat(), today)

        open_blockers = self.repos.blockers.find(user_id, {"status": {"$ne": "Resolved"}}, sort=[("identified_date", -1)], limit=5)
        names = self.repos.projects.names_by_id(user_id, {b.get("project_id") for b in open_blockers})
        for blocker in open_blockers:
            blocker["project_name"] = names.get(blocker.get("project_id"))

        return {
            "greeting": greeting(now_local.hour),
            "user_name": user["name"],
            "today": today,
            "today_label": format_long(today),
            "timezone": tz,
            "project_name": day["project_name"],
            "summary": day["summary"],
            "has_work": day["has_work"],
            "eod": day["eod"],
            "eod_time": settings["eod_time"],
            "auto_eod_enabled": settings["auto_eod_enabled"],
            "open_blockers": open_blockers,
            "open_blocker_count": self.repos.blockers.open_count(user_id),
            "open_ask_count": self.repos.dependencies.open_count(user_id),
            "recent_activity": [
                {"id": i["_id"], "description": i["description"], "work_date": i["work_date"], "status": i.get("status"),
                 "category": i.get("category"), "project_name": i.get("project_name"), "time_label": i["time_label"],
                 "updated_at": i["updated_at"]}
                for i in recent_items
            ],
            "recent_eods": [
                {"id": e["_id"], "work_date": e["work_date"], "status": e["status"], "subject": e.get("subject"),
                 "project_label": e.get("project_label"), "sent_at": e.get("sent_at"),
                 "sent_time_label": format_time(e["sent_at"], tz) if e.get("sent_at") else None}
                for e in recent_eods
            ],
            "days_logged_this_week": len(logged),
        }

    def calendar(self, user_id: ObjectId, year: int, month: int) -> dict:
        start, end = month_bounds(year, month)
        tz = self.settings.timezone(user_id)
        work_dates = self.repos.work_items.dates_with_items(user_id, start, end) | self.repos.work_logs.dates_with_content(user_id, start, end)
        eods = self.repos.eods.statuses_between(user_id, start, end)
        open_blocker_dates = {
            b["identified_date"] for b in self.repos.blockers.find(user_id, {"identified_date": {"$gte": start, "$lte": end}}, limit=1000)
        }

        days = []
        current = date.fromisoformat(start)
        last = date.fromisoformat(end)
        while current <= last:
            iso = current.isoformat()
            eod = eods.get(iso)
            status = eod["status"] if eod else EodStatus.NOT_GENERATED
            days.append({
                "date": iso,
                "has_work": iso in work_dates,
                "eod_status": status,
                "eod_generated": bool(eod and eod.get("current_version", 0) >= 1) or status in (EodStatus.GENERATED, EodStatus.SENT),
                "eod_sent": bool(eod and eod.get("sent_version")) or status == EodStatus.SENT,
                "eod_failed": status == EodStatus.FAILED,
                "has_blocker": iso in open_blocker_dates,
            })
            current += timedelta(days=1)
        return {"year": year, "month": month, "today": local_now(tz).date().isoformat(), "timezone": tz, "days": days}
