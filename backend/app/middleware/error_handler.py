"""Map exceptions to the standard error envelope without leaking internals."""
from __future__ import annotations

import logging

from flask import Flask, request
from pymongo.errors import PyMongoError
from werkzeug.exceptions import HTTPException

from ..utils.errors import AppError
from ..utils.responses import error

logger = logging.getLogger(__name__)

_HTTP_CODES = {
    400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED",
    413: "PAYLOAD_TOO_LARGE", 415: "UNSUPPORTED_MEDIA_TYPE", 429: "RATE_LIMITED",
}


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def handle_app_error(exc: AppError):
        if exc.status_code >= 500:
            logger.warning("Request failed", extra={"code": exc.code, "path": request.path, "status": exc.status_code})
        response, status = error(exc.code, exc.message, exc.status_code, exc.details)
        cookie_name = app.config["SETTINGS"].SESSION_COOKIE_NAME
        if exc.code == "UNAUTHORIZED" and request.cookies.get(cookie_name):
            # Expired or revoked session: drop the stale cookie so the frontend does not keep sending it.
            response.delete_cookie(cookie_name, path="/", httponly=True, samesite="Lax", secure=app.config["SETTINGS"].cookie_secure)
        return response, status

    @app.errorhandler(HTTPException)
    def handle_http(exc: HTTPException):
        status = exc.code or 500
        message = {404: "The requested endpoint was not found.", 405: "This method is not allowed for the endpoint."}.get(
            status, exc.description or "The request could not be processed."
        )
        return error(_HTTP_CODES.get(status, "HTTP_ERROR"), message, status)

    @app.errorhandler(PyMongoError)
    def handle_db(exc: PyMongoError):
        logger.exception("Database error", extra={"path": request.path})
        return error("DATABASE_ERROR", "The database is temporarily unavailable. Please try again.", 503)

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):
        logger.exception("Unhandled error", extra={"path": request.path, "method": request.method})
        return error("INTERNAL_ERROR", "Something went wrong on our side. Please try again.", 500)
