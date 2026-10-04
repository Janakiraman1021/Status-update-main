"""Structured JSON logging with redaction of sensitive fields."""
from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone

_SENSITIVE_KEYS = re.compile(r"pass(word)?|secret|token|api[_-]?key|authorization|cookie|csrf", re.IGNORECASE)
_RESERVED = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime"}


def redact(value):
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if _SENSITIVE_KEYS.search(str(k)) else redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extras = {k: v for k, v in record.__dict__.items() if k not in _RESERVED and not k.startswith("_")}
        if extras:
            payload.update(redact(extras))
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if any(getattr(h, "_worklog", False) for h in root.handlers):
        root.setLevel(level.upper())
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler._worklog = True  # type: ignore[attr-defined]
    root.handlers = [handler]
    root.setLevel(level.upper())
    for noisy in ("pymongo", "urllib3", "httpx", "httpcore", "apscheduler.executors.default", "werkzeug"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
