"""Request validation schemas. Every write endpoint validates its body here before touching the database."""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, TypeVar

from bson import ObjectId
from flask import request
from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, ValidationError, field_validator

from ..constants import (
    BLOCKER_STATUSES, DEPENDENCY_STATUSES, DEPENDENCY_TYPES, EOD_LENGTHS, EOD_TONES, THEMES, WORK_CATEGORIES, WORK_STATUSES,
)
from .datetime_utils import is_valid_date, is_valid_timezone, parse_hhmm
from .errors import NotFound, ValidationFailed

T = TypeVar("T", bound=BaseModel)

MAX_TEXT = 20000
MAX_LINE = 2000


def object_id(value: str, label: str = "resource") -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    if not isinstance(value, str) or not ObjectId.is_valid(value):
        raise NotFound(f"The requested {label} was not found.")
    return ObjectId(value)


def parse_body(model: type[T], partial_allowed: bool = False) -> T:
    if not request.is_json:
        raise ValidationFailed("Request body must be JSON.", code="INVALID_CONTENT_TYPE")
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValidationFailed("Request body must be a JSON object.")
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        details = {}
        for err in exc.errors():
            field = ".".join(str(p) for p in err["loc"]) or "body"
            details[field] = err["msg"].removeprefix("Value error, ")
        raise ValidationFailed("Some fields are invalid.", details=details) from exc


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.replace("\r\n", "\n").strip()


def _clean_or_none(value: Optional[str]) -> Optional[str]:
    return _clean(value) or None


def _required_text(value: str) -> str:
    value = _clean(value) or ""
    if not value:
        raise ValueError("This field cannot be empty")
    return value


def _date(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    if not is_valid_date(value):
        raise ValueError("Expected a valid date in YYYY-MM-DD format")
    return value


def _required_date(value: str) -> str:
    if not _date(value):
        raise ValueError("Date is required")
    return value


def _oid(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    if not ObjectId.is_valid(value):
        raise ValueError("Invalid identifier")
    return value


def _required_oid(value: str) -> str:
    if not ObjectId.is_valid(value):
        raise ValueError("Invalid identifier")
    return value


def _hhmm(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    parse_hhmm(value)
    return value


def _single_line(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = " ".join(value.split())
    if not value:
        raise ValueError("This field cannot be empty")
    return value


Text = Annotated[Optional[str], Field(default=None, max_length=MAX_TEXT), AfterValidator(_clean)]
OptionalLine = Annotated[Optional[str], Field(default=None, max_length=MAX_LINE), AfterValidator(_clean_or_none)]
RequiredLine = Annotated[str, Field(min_length=1, max_length=MAX_LINE), AfterValidator(_required_text)]
OptionalId = Annotated[Optional[str], Field(default=None), AfterValidator(_oid)]
RequiredDate = Annotated[str, AfterValidator(_required_date)]
OptionalDate = Annotated[Optional[str], Field(default=None), AfterValidator(_date)]
OptionalTime = Annotated[Optional[str], Field(default=None), AfterValidator(_hhmm)]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---- auth ---------------------------------------------------------------

class LoginRequest(Schema):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    remember: bool = False


# ---- work logs ----------------------------------------------------------

class WorkLogUpdate(Schema):
    project_id: OptionalId = None
    quick_notes: Text = None
    next_steps: Text = None
    learnings: Text = None
    meetings: Text = None
    metrics: Text = None


class WorkLogUpsert(WorkLogUpdate):
    work_date: RequiredDate


# ---- work items ---------------------------------------------------------

Category = Literal[tuple(WORK_CATEGORIES)]  # type: ignore[valid-type]
WorkStatus = Literal[tuple(WORK_STATUSES)]  # type: ignore[valid-type]


class WorkItemUpdate(Schema):
    description: Optional[RequiredLine] = None
    project_id: OptionalId = None
    category: Optional[Category] = None
    status: Optional[WorkStatus] = None
    time: OptionalTime = None


class WorkItemCreate(WorkItemUpdate):
    work_date: RequiredDate
    description: RequiredLine


class WorkItemBulkCreate(Schema):
    work_date: RequiredDate
    items: list[WorkItemUpdate] = Field(min_length=1, max_length=100)


# ---- projects -----------------------------------------------------------

ProjectName = Annotated[str, Field(min_length=1, max_length=120), AfterValidator(_single_line)]


class ProjectCreate(Schema):
    name: ProjectName
    description: Annotated[Optional[str], Field(default=None, max_length=2000), AfterValidator(_clean_or_none)] = None


class ProjectUpdate(Schema):
    name: Optional[ProjectName] = None
    description: Annotated[Optional[str], Field(default=None, max_length=2000), AfterValidator(_clean_or_none)] = None
    status: Optional[Literal["Active", "Archived"]] = None


ProjectProgress = Literal["On track", "Needs help", "Delayed", "Done"]


class ProjectStatusUpsert(Schema):
    project_id: Annotated[str, AfterValidator(_required_oid)]
    work_date: RequiredDate
    status: ProjectProgress = "On track"
    daily_update: Annotated[str, Field(max_length=MAX_TEXT), AfterValidator(_required_text)]
    next_step: Text = None
    help_needed: Text = None


# ---- blockers / dependencies -------------------------------------------

BlockerStatus = Literal[tuple(BLOCKER_STATUSES)]  # type: ignore[valid-type]
DependencyType = Literal[tuple(DEPENDENCY_TYPES)]  # type: ignore[valid-type]
DependencyStatus = Literal[tuple(DEPENDENCY_STATUSES)]  # type: ignore[valid-type]
ShortText = Annotated[Optional[str], Field(default=None, max_length=500), AfterValidator(_clean_or_none)]


class BlockerUpdate(Schema):
    description: Optional[RequiredLine] = None
    project_id: OptionalId = None
    status: Optional[BlockerStatus] = None
    dependency: ShortText = None
    expected_resolution: OptionalDate = None
    resolved_date: OptionalDate = None


class BlockerCreate(Schema):
    description: RequiredLine
    project_id: OptionalId = None
    identified_date: RequiredDate
    status: BlockerStatus = "Open"
    dependency: ShortText = None
    expected_resolution: OptionalDate = None


class DependencyUpdate(Schema):
    description: Optional[RequiredLine] = None
    type: Optional[DependencyType] = None
    owner: ShortText = None
    status: Optional[DependencyStatus] = None
    project_id: OptionalId = None


class DependencyCreate(Schema):
    description: RequiredLine
    type: DependencyType = "Dependency"
    owner: ShortText = None
    status: DependencyStatus = "Open"
    project_id: OptionalId = None
    created_date: RequiredDate


# ---- EOD ----------------------------------------------------------------

class Recipients(Schema):
    to: list[EmailStr] = Field(default_factory=list, max_length=50)
    cc: list[EmailStr] = Field(default_factory=list, max_length=50)
    bcc: list[EmailStr] = Field(default_factory=list, max_length=50)


EodLength = Literal[tuple(EOD_LENGTHS)]  # type: ignore[valid-type]
EodTone = Literal[tuple(EOD_TONES)]  # type: ignore[valid-type]


class EodOptions(Schema):
    """Per-generation choices; anything omitted falls back to the user's defaults in Settings."""

    length: Optional[EodLength] = None
    tone: Optional[EodTone] = None


class EodGenerate(EodOptions):
    work_date: RequiredDate


class EodUpdate(Schema):
    subject: Optional[str] = Field(default=None, min_length=1, max_length=300)
    body: Optional[str] = Field(default=None, min_length=1, max_length=50000)
    recipients: Optional[Recipients] = None

    @field_validator("subject")
    @classmethod
    def _v_subject(cls, v):
        if v is None:
            return v
        v = " ".join(v.split())
        if not v:
            raise ValueError("Subject cannot be empty")
        return v

    @field_validator("body")
    @classmethod
    def _v_body(cls, v):
        if v is None:
            return v
        v = v.replace("\r\n", "\n").strip()
        if not v:
            raise ValueError("Report body cannot be empty")
        return v


class EodSend(Schema):
    recipients: Optional[Recipients] = None
    resend: bool = False


# ---- settings -----------------------------------------------------------

class SettingsUpdate(Schema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    timezone: Optional[str] = None
    default_project_id: Optional[str] = None
    eod_time: Optional[str] = None
    auto_eod_enabled: Optional[bool] = None
    reminder_enabled: Optional[bool] = None
    reminder_minutes_before: Optional[int] = Field(default=None, ge=5, le=240)
    recipients: Optional[Recipients] = None
    eod_length: Optional[EodLength] = None
    eod_tone: Optional[EodTone] = None
    theme: Optional[Literal[tuple(THEMES)]] = None  # type: ignore[valid-type]
    signature_name: Optional[str] = Field(default=None, max_length=120)

    @field_validator("name")
    @classmethod
    def _v_name(cls, v):
        if v is None:
            return v
        v = " ".join(v.split())
        if not v:
            raise ValueError("Name cannot be empty")
        return v

    @field_validator("timezone")
    @classmethod
    def _v_tz(cls, v):
        if v is not None and not is_valid_timezone(v):
            raise ValueError("Unknown timezone")
        return v

    @field_validator("eod_time")
    @classmethod
    def _v_time(cls, v):
        if v is not None:
            parse_hhmm(v)
        return v

    @field_validator("default_project_id")
    @classmethod
    def _v_project(cls, v):
        return _oid(v)

    @field_validator("signature_name")
    @classmethod
    def _v_sig(cls, v):
        return _clean_or_none(v)


class TestEmailRequest(Schema):
    to: Optional[EmailStr] = None


class CategorizeRequest(Schema):
    text: str = Field(min_length=1, max_length=MAX_TEXT)


def pagination_args(default_limit: int = 20, max_limit: int = 100) -> tuple[int, int]:
    try:
        page = max(1, int(request.args.get("page", 1)))
        limit = int(request.args.get("limit", default_limit))
    except ValueError as exc:
        raise ValidationFailed("page and limit must be integers.") from exc
    return page, max(1, min(limit, max_limit))


def optional_choice(name: str, choices: list[str]) -> Optional[str]:
    value = request.args.get(name)
    if value in (None, ""):
        return None
    if value not in choices:
        raise ValidationFailed(f"Invalid {name}.", details={name: f"Must be one of: {', '.join(choices)}"})
    return value


def optional_date_arg(name: str) -> Optional[str]:
    value = request.args.get(name)
    if value in (None, ""):
        return None
    if not is_valid_date(value):
        raise ValidationFailed(f"Invalid {name}. Expected YYYY-MM-DD.")
    return value


def dump(model: BaseModel) -> dict[str, Any]:
    """Only the fields the client actually sent (supports partial updates and explicit nulls)."""
    return model.model_dump(exclude_unset=True)
