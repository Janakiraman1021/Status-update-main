"""Timezone-aware date helpers. Timestamps are stored in UTC; work dates are user-local YYYY-MM-DD strings."""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from .errors import ValidationFailed

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_zone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValidationFailed(f"Unknown timezone: {tz_name}") from exc


def is_valid_timezone(tz_name: str) -> bool:
    try:
        ZoneInfo(tz_name)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def list_timezones() -> list[str]:
    return sorted(available_timezones())


def parse_date(value: str, field: str = "date") -> date:
    if not isinstance(value, str) or not _DATE_RE.match(value):
        raise ValidationFailed(f"Invalid {field}. Expected YYYY-MM-DD.", details={field: "Expected YYYY-MM-DD"})
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationFailed(f"Invalid {field}.", details={field: "Not a real calendar date"}) from exc


def is_valid_date(value: str) -> bool:
    try:
        parse_date(value)
        return True
    except ValidationFailed:
        return False


def parse_hhmm(value: str) -> time:
    match = _TIME_RE.match(value or "")
    if not match:
        raise ValidationFailed("Invalid time. Expected HH:MM (24-hour).")
    return time(int(match.group(1)), int(match.group(2)))


def local_now(tz_name: str, now: datetime | None = None) -> datetime:
    return (now or utcnow()).astimezone(get_zone(tz_name))


def local_today(tz_name: str, now: datetime | None = None) -> str:
    return local_now(tz_name, now).date().isoformat()


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def local_datetime(work_date: str, hhmm: str, tz_name: str) -> datetime:
    """Build an aware datetime for a local date + HH:MM in the given zone."""
    return datetime.combine(parse_date(work_date), parse_hhmm(hhmm), tzinfo=get_zone(tz_name))


def default_entry_timestamp(work_date: str, tz_name: str, now: datetime | None = None) -> datetime:
    """Entries added for today get the current time; back-filled dates get 09:00 local on that date."""
    now = now or utcnow()
    if local_today(tz_name, now) == work_date:
        return now
    return to_utc(local_datetime(work_date, "09:00", tz_name))


def format_long(work_date: str) -> str:
    return parse_date(work_date).strftime("%d %B %Y")


def format_short(work_date: str) -> str:
    return parse_date(work_date).strftime("%d %b %Y")


def format_time(value: datetime, tz_name: str) -> str:
    return to_utc(value).astimezone(get_zone(tz_name)).strftime("%I:%M %p").lstrip("0")


def month_bounds(year: int, month: int) -> tuple[str, str]:
    if not (1 <= month <= 12) or not (1970 <= year <= 2200):
        raise ValidationFailed("Invalid year or month.")
    start = date(year, month, 1)
    end = (date(year + (month // 12), (month % 12) + 1, 1)) - timedelta(days=1)
    return start.isoformat(), end.isoformat()
