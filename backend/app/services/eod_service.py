"""EOD generation, versioning, editing and delivery.

Integrity rules:
  * One report per user per local work date (unique index).
  * Every generation / regeneration / post-send edit creates a new immutable version.
    Only an unsent manual edit is updated in place.
  * A sent version is never modified. Once a report is SENT it stays SENT; later versions
    are visible as unsent changes and can only go out through an explicit resend.
  * Sending is claimed atomically (GENERATED/FAILED -> SENDING), so a report can never be
    emailed twice by concurrent callers or a re-running scheduler.
"""
from __future__ import annotations

import logging
from typing import Any

from bson import ObjectId

from ..constants import EodFailure, EodStatus
from ..repositories import Repositories
from ..utils.datetime_utils import format_long, format_short, format_time, is_valid_date, to_utc, utcnow
from ..utils.errors import AppError, Conflict, NotFound
from .ai_service import AIError, AIProvider, GenerationOptions, unsupported_numbers
from .email_service import EmailService, InlineImage
from .eod_renderer import LOGO_CID, EmailTheme, body_to_html, build_subject, draft_to_body
from .settings_service import SettingsService
from .work_log_service import WorkLogService

logger = logging.getLogger(__name__)


class EodService:
    def __init__(self, repos: Repositories, ai: AIProvider, email: EmailService, settings: SettingsService, work_logs: WorkLogService,
                 theme: EmailTheme | None = None):
        self.repos = repos
        self.ai = ai
        self.email = email
        self.settings = settings
        self.work_logs = work_logs
        self.theme = theme or EmailTheme()

    def render_html(self, user: dict, report: dict, subject: str, body: str, for_email: bool = False) -> tuple[str, list[InlineImage]]:
        """Branded HTML with the date / project / sender strip.

        For sending, the logo file travels inside the email (cid:) so it shows without remote-image prompts;
        for the in-app preview it is embedded as a data URI.
        """
        prefs = self.settings.get(user["_id"])
        meta = {
            "date_label": format_long(report["work_date"]),
            "project": report.get("project_label"),
            "sender": prefs.get("signature_name") or user["name"],
        }
        images: list[InlineImage] = []
        logo_src = None
        logo = self.theme.logo_image()
        if logo:
            if for_email:
                images.append(InlineImage(cid=LOGO_CID, data=logo[0], mime_type=logo[1]))
                logo_src = f"cid:{LOGO_CID}"
            else:
                logo_src = self.theme.logo_data_uri()
        return body_to_html(body, subject, self.theme, meta, logo_src), images

    # -- context -------------------------------------------------------------

    def project_label(self, user_id: ObjectId, log: dict | None, items: list[dict]) -> str | None:
        if log and log.get("project_id"):
            names = self.repos.projects.names_by_id(user_id, {log["project_id"]})
            if names:
                return names[log["project_id"]]
        names = list(dict.fromkeys(i["project_name"] for i in items if i.get("project_name")))
        if len(names) == 1:
            return names[0]
        if len(names) == 2:
            return f"{names[0]} / {names[1]}"
        if names:
            return "Multiple Projects"
        return None

    def build_context(self, user: dict, work_date: str) -> tuple[dict, str, str | None]:
        """Collect everything the user recorded for the date. Returns (context, raw source text, project label)."""
        user_id = user["_id"]
        settings = self.settings.get(user_id)
        tz = settings["timezone"]
        log = self.repos.work_logs.by_date(user_id, work_date) or {}
        items = self.work_logs.decorate_items(user_id, self.repos.work_items.for_date(user_id, work_date), tz)
        blockers = [b for b in self.repos.blockers.relevant_for_date(user_id, work_date) if b["status"] != "Resolved" or b.get("resolved_date") == work_date]
        deps = [d for d in self.repos.dependencies.relevant_for_date(user_id, work_date) if d["status"] != "Resolved" or d.get("resolved_date") == work_date]
        label = self.project_label(user_id, log, items)

        context: dict[str, Any] = {
            "date": format_long(work_date),
            "user_name": settings.get("signature_name") or user["name"],
            "project": label,
            "quick_notes": log.get("quick_notes"),
            "entries": [
                {"time": i["time_label"], "description": i["description"], "project": i.get("project_name"),
                 "category": i.get("category"), "status": i.get("status")}
                for i in items
            ],
            "blockers": [
                {"description": b["description"], "status": b["status"], "dependency": b.get("dependency"),
                 "expected_resolution": b.get("expected_resolution"), "identified_date": b["identified_date"]}
                for b in blockers
            ],
            "dependencies": [
                {"description": d["description"], "type": d["type"], "owner": d.get("owner"), "status": d["status"]}
                for d in deps
            ],
            "next_steps": log.get("next_steps"),
            "learnings": log.get("learnings"),
            "meetings": log.get("meetings"),
            "metrics": log.get("metrics"),
        }
        context = {k: v for k, v in context.items() if v not in (None, "", [])}
        source_parts = [str(v) for k, v in context.items() if isinstance(v, str)]
        for key in ("entries", "blockers", "dependencies"):
            for row in context.get(key, []):
                source_parts.extend(str(v) for v in row.values() if v)
        source_parts.extend([work_date, format_short(work_date)])
        return context, "\n".join(source_parts), label

    # -- generation ----------------------------------------------------------

    def generate(self, user: dict, work_date: str, actor: str = "user", options: dict | None = None) -> dict:
        user_id = user["_id"]
        if not self.work_logs.has_work(user_id, work_date):
            raise AppError("No work has been logged for this date yet.", code="NO_WORK_LOGGED", status_code=422)
        now = utcnow()
        before = self.repos.eods.claim_generation(user_id, work_date, now)
        if before is None:
            raise Conflict("This EOD is currently being generated or sent. Please wait.", code="EOD_BUSY")
        report = self.repos.eods.by_date(user_id, work_date)
        logger.info("EOD generation started", extra={"event": "eod.generate", "user_id": str(user_id), "work_date": work_date, "actor": actor})

        try:
            context, source_text, label = self.build_context(user, work_date)
            gen_options = self.resolve_options(user_id, options)
            draft = self.ai.generate_eod(context, gen_options)
        except AIError as exc:
            return self._generation_failed(report, str(exc))
        except Exception:
            logger.exception("EOD generation crashed", extra={"user_id": str(user_id), "work_date": work_date})
            return self._generation_failed(report, "An unexpected error occurred while generating the report.")

        body = draft_to_body(draft, context.get("user_name") or user["name"])
        subject = build_subject(format_short(work_date), label)
        warnings = [f"'{n}' does not appear in your notes. Please verify it." for n in unsupported_numbers(body, source_text)]
        version = report.get("current_version", 0) + 1
        self.repos.eod_versions.add(user_id, report["_id"], work_date, version, {
            "subject": subject, "body": body, "source": "generated" if version == 1 else "regenerated",
            "created_by": str(user_id) if actor == "user" else actor, "ai_provider": self.ai.name, "ai_model": self.ai.model,
            "draft": draft.to_dict(), "warnings": warnings,
            "options": {"length": gen_options.length, "tone": gen_options.tone},
        })
        updated = self.repos.eods.set_state(report["_id"], {
            "status": EodStatus.SENT if report.get("sent_version") else EodStatus.GENERATED,
            "current_version": version, "subject": subject, "body": body, "project_label": label,
            "generated_at": utcnow(), "generated_by": actor, "warnings": warnings, "last_error": None,
            "options": {"length": gen_options.length, "tone": gen_options.tone},
        }, unset=("generating_started_at",))
        logger.info("EOD generated", extra={"event": "eod.generated", "user_id": str(user_id), "work_date": work_date, "version": version})
        return updated

    def _generation_failed(self, report: dict, message: str) -> dict:
        has_previous = report.get("current_version", 0) >= 1
        status = (EodStatus.SENT if report.get("sent_version") else EodStatus.GENERATED) if has_previous else EodStatus.FAILED
        self.repos.eods.set_state(report["_id"], {
            "status": status,
            "last_error": {"stage": "GENERATION", "code": EodFailure.GENERATION, "message": message, "at": utcnow()},
        }, unset=("generating_started_at",))
        logger.warning("EOD generation failed", extra={"event": "eod.generation_failed", "user_id": str(report["user_id"]),
                                                        "work_date": report["work_date"], "error": message})
        raise AppError(message, code=EodFailure.GENERATION, status_code=502)

    def regenerate(self, user: dict, eod_id: ObjectId, options: dict | None = None) -> dict:
        report = self._get(user["_id"], eod_id)
        return self.generate(user, report["work_date"], options=options)

    def resolve_options(self, user_id: ObjectId, options: dict | None) -> GenerationOptions:
        """Explicit choices for this generation win; otherwise the defaults from Settings apply."""
        prefs = self.settings.get(user_id)
        options = options or {}
        return GenerationOptions.from_any({"length": options.get("length") or prefs["eod_length"],
                                           "tone": options.get("tone") or prefs["eod_tone"]})

    # -- editing -------------------------------------------------------------

    def update(self, user: dict, eod_id: ObjectId, data: dict) -> dict:
        user_id = user["_id"]
        report = self._get(user_id, eod_id)
        if report["status"] in (EodStatus.GENERATING, EodStatus.SENDING):
            raise Conflict("This EOD is busy. Please wait a moment and try again.", code="EOD_BUSY")
        fields: dict[str, Any] = {}
        if data.get("recipients") is not None:
            fields["recipients"] = data["recipients"]

        subject, body = data.get("subject"), data.get("body")
        if subject is not None or body is not None:
            if report.get("current_version", 0) < 1:
                raise Conflict("Generate the EOD before editing it.", code="EOD_NOT_GENERATED")
            current = self.repos.eod_versions.current(user_id, eod_id)
            new_subject = subject if subject is not None else current["subject"]
            new_body = body if body is not None else current["body"]
            if (new_subject, new_body) != (current["subject"], current["body"]):
                if current.get("source") == "edited" and not current.get("sent_at") and current.get("created_by") == str(user_id):
                    self.repos.eod_versions.update(user_id, current["_id"], {"subject": new_subject, "body": new_body, "edited_at": utcnow()})
                    version = current["version"]
                else:
                    version = report["current_version"] + 1
                    self.repos.eod_versions.add(user_id, eod_id, report["work_date"], version, {
                        "subject": new_subject, "body": new_body, "source": "edited", "created_by": str(user_id),
                        "based_on_version": current["version"], "warnings": [],
                    })
                fields.update(subject=new_subject, body=new_body, current_version=version, edited_at=utcnow(), warnings=[])
                logger.info("EOD edited", extra={"event": "eod.edited", "user_id": str(user_id), "eod_id": str(eod_id), "version": version})
        if fields:
            report = self.repos.eods.set_state(eod_id, fields)
        return report

    # -- sending -------------------------------------------------------------

    def send(self, user: dict, eod_id: ObjectId, recipients: dict | None = None, resend: bool = False, actor: str = "user") -> dict:
        user_id = user["_id"]
        report = self._get(user_id, eod_id)
        if recipients is not None:
            self.repos.eods.set_state(eod_id, {"recipients": recipients})
            report["recipients"] = recipients

        claimed = self.repos.eods.claim_send(user_id, eod_id, allow_resend=resend, now=utcnow())
        if not claimed:
            current = self._get(user_id, eod_id)
            status = current["status"]
            if status == EodStatus.SENT:
                raise Conflict("This EOD has already been sent.", code="EOD_ALREADY_SENT")
            if status == EodStatus.SENDING:
                raise Conflict("This EOD is already being sent.", code="EOD_SEND_IN_PROGRESS")
            if status == EodStatus.GENERATING:
                raise Conflict("This EOD is still being generated.", code="EOD_BUSY")
            raise Conflict("Generate the EOD before sending it.", code="EOD_NOT_GENERATED")

        version = self.repos.eod_versions.current(user_id, eod_id)
        to = self.settings.resolve_recipients(user, report.get("recipients"))
        logger.info("EOD send attempt", extra={"event": "eod.send", "user_id": str(user_id), "eod_id": str(eod_id),
                                                "version": version["version"], "actor": actor})
        html_body, inline_images = self.render_html(user, report, version["subject"], version["body"], for_email=True)
        result = self.email.send_eod(
            user_id=user_id, eod_id=eod_id, version=version["version"], to=to["to"], cc=to["cc"], bcc=to["bcc"],
            subject=version["subject"], html_body=html_body, text_body=version["body"], reply_to=user["email"],
            inline_images=inline_images,
        )
        now = utcnow()
        if result.success:
            self.repos.eod_versions.col.update_one(
                {"_id": version["_id"], "user_id": user_id},
                {"$set": {"sent_at": now, "sent_to": to, "sent_by": actor, "message_id": result.message_id}},
            )
            updated = self.repos.eods.set_state(eod_id, {
                "status": EodStatus.SENT, "sent_at": now, "sent_version": version["version"], "sent_to": to,
                "sent_by": actor, "last_error": None,
            }, unset=("sending_started_at",))
            logger.info("EOD sent", extra={"event": "eod.sent", "user_id": str(user_id), "eod_id": str(eod_id), "version": version["version"]})
            return updated

        was_sent = claimed["status"] == EodStatus.SENT
        self.repos.eods.set_state(eod_id, {
            "status": EodStatus.SENT if was_sent else EodStatus.FAILED,
            "last_error": {"stage": "EMAIL", "code": EodFailure.EMAIL, "message": result.error, "at": now},
        }, unset=("sending_started_at",))
        logger.warning("EOD email failed", extra={"event": "eod.email_failed", "user_id": str(user_id), "eod_id": str(eod_id), "error": result.error})
        raise AppError("Unable to send EOD. Retry.", code=EodFailure.EMAIL, status_code=502, details={"reason": result.error})

    # -- reads ---------------------------------------------------------------

    def _get(self, user_id: ObjectId, eod_id: ObjectId) -> dict:
        report = self.repos.eods.get(user_id, eod_id)
        if not report:
            raise NotFound("EOD report not found.", code="EOD_NOT_FOUND")
        return report

    def view(self, user: dict, key: str) -> dict:
        """Full EOD view for a date (YYYY-MM-DD) or a report id."""
        user_id = user["_id"]
        if is_valid_date(key):
            report = self.repos.eods.by_date(user_id, key)
            work_date = key
        elif ObjectId.is_valid(key):
            report = self._get(user_id, ObjectId(key))
            work_date = report["work_date"]
        else:
            raise NotFound("EOD report not found.", code="EOD_NOT_FOUND")

        settings = self.settings.get(user_id)
        tz = settings["timezone"]
        source_inputs, _, _ = self.build_context(user, work_date)
        default_recipients = self.settings.resolve_recipients(user)
        result: dict[str, Any] = {
            "work_date": work_date,
            "date_label": format_long(work_date),
            "has_work": self.work_logs.has_work(user_id, work_date),
            "source_inputs": source_inputs,
            "default_recipients": default_recipients,
            "default_options": {"length": settings["eod_length"], "tone": settings["eod_tone"]},
            "ai_provider": self.ai.name,
            "report": None,
            "versions": [],
            "current": None,
            "deliveries": [],
            "outdated": False,
        }
        if not report:
            return result

        versions = self.repos.eod_versions.for_report(user_id, report["_id"])
        result["report"] = {**report, "recipients": report.get("recipients") or default_recipients,
                            "has_unsent_changes": bool(report.get("sent_version")) and report.get("current_version") != report.get("sent_version")}
        result["versions"] = [
            {k: v.get(k) for k in ("_id", "version", "source", "is_current", "created_at", "created_by", "sent_at", "subject", "ai_provider", "ai_model", "based_on_version", "options")}
            for v in versions
        ]
        result["current"] = next((v for v in versions if v.get("is_current")), None)
        if result["current"]:
            result["current"].pop("draft", None)
        result["deliveries"] = [
            {k: log.get(k) for k in ("_id", "created_at", "success", "to", "cc", "bcc", "error", "provider", "reference")}
            for log in self.repos.email_logs.for_reference(user_id, "eod_id", report["_id"])
        ]
        changed = self.work_logs.last_change(user_id, work_date)
        if changed and report.get("generated_at"):
            result["outdated"] = changed > to_utc(report["generated_at"])
        if report.get("sent_at"):
            result["report"]["sent_time_label"] = format_time(report["sent_at"], tz)
        return result

    def version_detail(self, user: dict, eod_id: ObjectId, version: int) -> dict:
        self._get(user["_id"], eod_id)
        doc = self.repos.eod_versions.by_number(user["_id"], eod_id, version)
        if not doc:
            raise NotFound("Version not found.", code="EOD_VERSION_NOT_FOUND")
        doc.pop("draft", None)
        return doc

    def preview_html(self, user: dict, eod_id: ObjectId) -> str:
        report = self._get(user["_id"], eod_id)
        if not report.get("body"):
            raise Conflict("Generate the EOD before previewing it.", code="EOD_NOT_GENERATED")
        return self.render_html(user, report, report["subject"], report["body"])[0]
