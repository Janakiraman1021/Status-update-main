"""Convert Mongo documents into JSON-safe structures."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from bson import ObjectId


def to_json(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key == "_id":
                out["id"] = to_json(item)
            else:
                out[key] = to_json(item)
        return out
    if isinstance(value, (list, tuple)):
        return [to_json(item) for item in value]
    return value
