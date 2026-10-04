"""Application error types mapped to consistent API error responses."""
from __future__ import annotations

from typing import Any


class AppError(Exception):
    status_code = 400
    code = "BAD_REQUEST"
    message = "The request could not be processed."

    def __init__(self, message: str | None = None, code: str | None = None, status_code: int | None = None, details: Any = None):
        super().__init__(message or self.message)
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details


class ValidationFailed(AppError):
    status_code = 400
    code = "VALIDATION_ERROR"
    message = "Some fields are invalid."


class Unauthorized(AppError):
    status_code = 401
    code = "UNAUTHORIZED"
    message = "Please sign in to continue."


class Forbidden(AppError):
    status_code = 403
    code = "FORBIDDEN"
    message = "You do not have access to this resource."


class NotFound(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "The requested resource was not found."


class Conflict(AppError):
    status_code = 409
    code = "CONFLICT"
    message = "The request conflicts with the current state."


class RateLimited(AppError):
    status_code = 429
    code = "RATE_LIMITED"
    message = "Too many attempts. Please try again later."


class ServiceUnavailable(AppError):
    status_code = 503
    code = "SERVICE_UNAVAILABLE"
    message = "A required service is unavailable. Please try again."
