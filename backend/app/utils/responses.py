"""Consistent JSON response envelopes."""
from __future__ import annotations

from typing import Any

from flask import jsonify

from .serialization import to_json


def ok(data: Any = None, status: int = 200, meta: dict | None = None):
    body: dict[str, Any] = {"success": True, "data": to_json(data)}
    if meta is not None:
        body["meta"] = to_json(meta)
    return jsonify(body), status


def error(code: str, message: str, status: int, details: Any = None):
    payload: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        payload["details"] = to_json(details)
    return jsonify({"success": False, "error": payload}), status
