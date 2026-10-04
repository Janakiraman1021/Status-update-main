from __future__ import annotations

from bson import ObjectId

from ..constants import LEGACY_STYLE_TO_LENGTH
from ..repositories import Repositories
from ..utils.errors import ValidationFailed

_SETTINGS_FIELDS = {
    "timezone", "default_project_id", "eod_time", "auto_eod_enabled", "reminder_enabled",
    "reminder_minutes_before", "recipients", "eod_length", "eod_tone", "theme", "signature_name",
}


class SettingsService:
    def __init__(self, repos: Repositories, config):
        self.repos = repos
        self.config = config

    def defaults(self) -> dict:
        return {
            "timezone": self.config.DEFAULT_TIMEZONE,
            "default_project_id": None,
            "eod_time": self.config.EOD_DEFAULT_TIME,
            "auto_eod_enabled": False,
            "reminder_enabled": False,
            "reminder_minutes_before": 30,
            "recipients": {"to": [], "cc": [], "bcc": []},
            "eod_length": "standard",
            "eod_tone": "executive",
            "theme": "system",
            "signature_name": None,
        }

    def get(self, user_id: ObjectId) -> dict:
        stored = self.repos.settings.get(user_id) or {}
        merged = {**self.defaults(), **{k: v for k, v in stored.items() if k in _SETTINGS_FIELDS}}
        if "eod_length" not in stored and stored.get("ai_style") in LEGACY_STYLE_TO_LENGTH:
            merged["eod_length"] = LEGACY_STYLE_TO_LENGTH[stored["ai_style"]]
        merged["recipients"] = {**self.defaults()["recipients"], **(merged.get("recipients") or {})}
        return merged

    def timezone(self, user_id: ObjectId) -> str:
        return self.get(user_id)["timezone"]

    def update(self, user: dict, data: dict) -> dict:
        if "name" in data and data["name"]:
            self.repos.users.update(user["_id"], {"name": data["name"]})
            user["name"] = data["name"]
        fields = {k: v for k, v in data.items() if k in _SETTINGS_FIELDS}
        if fields.get("default_project_id"):
            project = self.repos.projects.get(user["_id"], ObjectId(fields["default_project_id"]))
            if not project:
                raise ValidationFailed("Default project not found.", details={"default_project_id": "Unknown project"})
            fields["default_project_id"] = project["_id"]
        for key in ("timezone", "eod_time", "eod_length", "eod_tone", "theme", "reminder_minutes_before"):
            if key in fields and fields[key] is None:
                fields.pop(key)
        if fields:
            self.repos.settings.upsert(user["_id"], fields, self.defaults())
        return self.get(user["_id"])

    def resolve_recipients(self, user: dict, override: dict | None = None) -> dict:
        """Explicit recipients win, then the user's defaults, then the user's own address."""
        for source in (override, self.get(user["_id"])["recipients"]):
            if source and source.get("to"):
                return {"to": list(source["to"]), "cc": list(source.get("cc") or []), "bcc": list(source.get("bcc") or [])}
        return {"to": [user["email"]], "cc": [], "bcc": []}
