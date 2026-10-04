"""Automatic EOD processing and reminders. Safe to run repeatedly and from several processes at once."""
from __future__ import annotations

import html
import logging
from datetime import datetime, timedelta

from ..constants import EodFailure, EodStatus
from ..repositories import Repositories
from ..utils.datetime_utils import format_long, local_datetime, local_now, utcnow
from ..utils.errors import AppError
from .email_service import EmailService, OutgoingEmail
from .eod_service import EodService
from .settings_service import SettingsService
from .work_log_service import WorkLogService

logger = logging.getLogger(__name__)

STALE_SENDING_AFTER = timedelta(minutes=15)


class SchedulerService:
    def __init__(self, repos: Repositories, settings: SettingsService, work_logs: WorkLogService, eods: EodService,
                 email: EmailService, config):
        self.repos = repos
        self.settings = settings
        self.work_logs = work_logs
        self.eods = eods
        self.email = email
        self.config = config

    def run_tick(self, now: datetime | None = None) -> dict:
        now = now or utcnow()
        stats: dict[str, int] = {}
        self.recover_stale_sending(now)
        for settings_doc in self.repos.settings.automation_candidates():
            try:
                for outcome in self.process_user(settings_doc["user_id"], now):
                    stats[outcome] = stats.get(outcome, 0) + 1
            except Exception:
                logger.exception("Scheduler failed for user", extra={"user_id": str(settings_doc.get("user_id"))})
                stats["error"] = stats.get("error", 0) + 1
        if stats:
            logger.info("Scheduler tick", extra={"event": "scheduler.tick", "stats": stats})
        return stats

    def process_user(self, user_id, now: datetime) -> list[str]:
        user = self.repos.users.by_id(user_id)
        if not user:
            return []
        settings = self.settings.get(user_id)
        tz = settings["timezone"]
        current = local_now(tz, now)
        today = current.date().isoformat()
        eod_at = local_datetime(today, settings["eod_time"], tz)
        outcomes = []

        if settings["reminder_enabled"]:
            remind_at = eod_at - timedelta(minutes=settings["reminder_minutes_before"])
            if remind_at <= current < eod_at:
                outcomes.append(self.maybe_remind(user, today, now))
        if settings["auto_eod_enabled"] and current >= eod_at:
            outcomes.append(self.run_auto_eod(user, today, now))
        return [o for o in outcomes if o]

    def maybe_remind(self, user: dict, work_date: str, now: datetime) -> str | None:
        if self.work_logs.has_work(user["_id"], work_date):
            return None
        if not self.repos.locks.acquire(f"reminder:{user['_id']}:{work_date}", now + timedelta(days=3), {"user_id": user["_id"]}):
            return None
        message = "You haven't documented today's work yet. Please update your WorkLog before EOD."
        link = f"{self.config.FRONTEND_URL.rstrip('/')}/work-log/{work_date}"
        email = OutgoingEmail(
            to=[user["email"]],
            subject=f"Reminder: update your WorkLog for {format_long(work_date)}",
            text=f"Hi {user['name']},\n\n{message}\n\n{link}\n",
            html=(f'<p style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#26313f;">Hi {html.escape(user["name"])},</p>'
                  f'<p style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#26313f;">{message}</p>'
                  f'<p><a href="{html.escape(link)}" style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;">Open today\'s work log</a></p>'),
        )
        result = self.email.send_email(email, user_id=user["_id"], kind="reminder", reference={"work_date": work_date})
        return "reminder_sent" if result.success else "reminder_failed"

    def run_auto_eod(self, user: dict, work_date: str, now: datetime) -> str:
        user_id = user["_id"]
        existing = self.repos.eods.by_date(user_id, work_date)
        if existing and existing["status"] in (EodStatus.SENT, EodStatus.SENDING):
            return "skipped_already_sent"
        if not self.work_logs.has_work(user_id, work_date):
            return "skipped_no_work"
        claim = self.repos.eods.claim_auto_attempt(
            user_id, work_date, now, self.config.EOD_MAX_AUTO_ATTEMPTS, timedelta(minutes=self.config.EOD_AUTO_RETRY_MINUTES)
        )
        if not claim:
            return "skipped_not_due"
        log_extra = {"user_id": str(user_id), "work_date": work_date, "attempt": claim.get("auto_attempts")}
        logger.info("Automatic EOD started", extra={"event": "scheduler.auto_eod", **log_extra})
        try:
            # Reuse an existing (possibly user-edited) version; only generate when there is none.
            if claim.get("current_version", 0) < 1:
                self.eods.generate(user, work_date, actor="scheduler")
            report = self.repos.eods.by_date(user_id, work_date)
            self.eods.send(user, report["_id"], actor="scheduler")
            return "auto_eod_sent"
        except AppError as exc:
            logger.warning("Automatic EOD failed", extra={"event": "scheduler.auto_eod_failed", "code": exc.code, **log_extra})
            return "auto_eod_failed"

    def recover_stale_sending(self, now: datetime) -> int:
        """A crash mid-send leaves SENDING behind. Delivery is unknown, so never retry automatically."""
        cutoff = now - STALE_SENDING_AFTER
        recovered = 0
        for report in self.repos.eods.stale_sending(cutoff):
            fields = {
                "status": EodStatus.SENT if report.get("sent_version") else EodStatus.FAILED,
                "auto_attempts": self.config.EOD_MAX_AUTO_ATTEMPTS,
                "last_error": {"stage": "EMAIL", "code": EodFailure.DELIVERY_UNKNOWN, "at": now,
                               "message": "Delivery could not be confirmed. Check your sent mail before retrying."},
            }
            if self.repos.eods.mark_stale_sending_unknown(report["_id"], cutoff, fields):
                recovered += 1
                logger.warning("Recovered stale SENDING report", extra={"eod_id": str(report["_id"])})
        return recovered
