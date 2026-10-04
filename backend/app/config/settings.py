"""Application configuration loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
_MANAGED_KEYS = "_WORKLOG_DOTENV_KEYS"


def load_env_file(path: Path = ENV_FILE) -> None:
    """Load backend/.env without overriding real environment variables.

    Keys that came from .env are remembered, so a reloaded child process (Flask dev reloader)
    re-reads the file instead of inheriting the parent's stale values — edits to .env apply on reload.
    """
    managed = set(filter(None, os.environ.get(_MANAGED_KEYS, "").split(",")))
    for key, value in dotenv_values(path).items():
        if value is None:
            continue
        if key not in os.environ or key in managed:
            os.environ[key] = value
            managed.add(key)
    os.environ[_MANAGED_KEYS] = ",".join(sorted(managed))


load_env_file()


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


def _str(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return value.strip() if value not in (None, "") else default


@dataclass
class Settings:
    FLASK_ENV: str = field(default_factory=lambda: _str("FLASK_ENV", "development"))
    SECRET_KEY: str = field(default_factory=lambda: _str("SECRET_KEY"))
    SESSION_SECRET: str = field(default_factory=lambda: _str("SESSION_SECRET"))

    MONGODB_URI: str = field(default_factory=lambda: _str("MONGODB_URI", "mongodb://localhost:27017"))
    MONGODB_DATABASE: str = field(default_factory=lambda: _str("MONGODB_DATABASE", "worklog"))

    # Single-user mode: the only account that can sign in. Created/updated at startup.
    APP_USER_EMAIL: str = field(default_factory=lambda: _str("APP_USER_EMAIL").lower())
    APP_USER_PASSWORD: str = field(default_factory=lambda: os.getenv("APP_USER_PASSWORD", ""))
    APP_USER_NAME: str = field(default_factory=lambda: _str("APP_USER_NAME", "WorkLog User"))

    SESSION_COOKIE_NAME: str = field(default_factory=lambda: _str("SESSION_COOKIE_NAME", "worklog_session"))
    SESSION_TTL_HOURS: int = field(default_factory=lambda: _int("SESSION_TTL_HOURS", 12))
    REMEMBER_TTL_DAYS: int = field(default_factory=lambda: _int("REMEMBER_TTL_DAYS", 30))
    COOKIE_SECURE: bool | None = field(default_factory=lambda: _bool("COOKIE_SECURE", False) if os.getenv("COOKIE_SECURE") else None)
    TRUST_PROXY: bool = field(default_factory=lambda: _bool("TRUST_PROXY", False))
    LOGIN_MAX_ATTEMPTS: int = field(default_factory=lambda: _int("LOGIN_MAX_ATTEMPTS", 5))
    LOGIN_WINDOW_SECONDS: int = field(default_factory=lambda: _int("LOGIN_WINDOW_SECONDS", 900))

    AI_PROVIDER: str = field(default_factory=lambda: _str("AI_PROVIDER", "local").lower())
    AI_API_KEY: str = field(default_factory=lambda: _str("AI_API_KEY"))
    AI_MODEL: str = field(default_factory=lambda: _str("AI_MODEL"))
    AI_BASE_URL: str = field(default_factory=lambda: _str("AI_BASE_URL"))
    AI_TIMEOUT_SECONDS: int = field(default_factory=lambda: _int("AI_TIMEOUT_SECONDS", 120))
    # Qwen reasoning effort on Groq: none (fastest), default, low, medium, high
    AI_REASONING_EFFORT: str = field(default_factory=lambda: _str("AI_REASONING_EFFORT", "none"))

    EMAIL_PROVIDER: str = field(default_factory=lambda: _str("EMAIL_PROVIDER", "console").lower())
    EMAIL_FROM: str = field(default_factory=lambda: _str("EMAIL_FROM"))
    EMAIL_FROM_NAME: str = field(default_factory=lambda: _str("EMAIL_FROM_NAME", "WorkLog"))
    # EOD email branding (colours as #RRGGBB; logo must be a public https URL)
    EMAIL_BRAND_NAME: str = field(default_factory=lambda: _str("EMAIL_BRAND_NAME", "Samunnati"))
    EMAIL_BRAND_PRIMARY: str = field(default_factory=lambda: _str("EMAIL_BRAND_PRIMARY"))
    EMAIL_BRAND_ACCENT: str = field(default_factory=lambda: _str("EMAIL_BRAND_ACCENT"))
    EMAIL_BRAND_SOFT: str = field(default_factory=lambda: _str("EMAIL_BRAND_SOFT"))
    EMAIL_BRAND_LOGO_URL: str = field(default_factory=lambda: _str("EMAIL_BRAND_LOGO_URL"))
    EMAIL_BRAND_LOGO_PATH: str = field(default_factory=lambda: _str("EMAIL_BRAND_LOGO_PATH", "assets/brand-logo.png"))
    EMAIL_BRAND_LEGAL_NAME: str = field(default_factory=lambda: _str("EMAIL_BRAND_LEGAL_NAME", "Samunnati Finance Private Limited"))
    EMAIL_BRAND_WEBSITE: str = field(default_factory=lambda: _str("EMAIL_BRAND_WEBSITE"))
    SMTP_HOST: str = field(default_factory=lambda: _str("SMTP_HOST"))
    SMTP_PORT: int = field(default_factory=lambda: _int("SMTP_PORT", 587))
    SMTP_USERNAME: str = field(default_factory=lambda: _str("SMTP_USERNAME"))
    SMTP_PASSWORD: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    SMTP_USE_TLS: bool = field(default_factory=lambda: _bool("SMTP_USE_TLS", True))
    SMTP_USE_SSL: bool = field(default_factory=lambda: _bool("SMTP_USE_SSL", False))
    SMTP_TIMEOUT_SECONDS: int = field(default_factory=lambda: _int("SMTP_TIMEOUT_SECONDS", 30))
    OUTBOX_DIR: str = field(default_factory=lambda: _str("OUTBOX_DIR", "outbox"))

    DEFAULT_TIMEZONE: str = field(default_factory=lambda: _str("DEFAULT_TIMEZONE", "Asia/Kolkata"))
    EOD_DEFAULT_TIME: str = field(default_factory=lambda: _str("EOD_DEFAULT_TIME", "18:30"))

    FRONTEND_URL: str = field(default_factory=lambda: _str("FRONTEND_URL", "http://localhost:3000"))
    SCHEDULER_ENABLED: bool = field(default_factory=lambda: _bool("SCHEDULER_ENABLED", True))
    SCHEDULER_INTERVAL_SECONDS: int = field(default_factory=lambda: _int("SCHEDULER_INTERVAL_SECONDS", 60))
    EOD_MAX_AUTO_ATTEMPTS: int = field(default_factory=lambda: _int("EOD_MAX_AUTO_ATTEMPTS", 3))
    EOD_AUTO_RETRY_MINUTES: int = field(default_factory=lambda: _int("EOD_AUTO_RETRY_MINUTES", 10))

    LOG_LEVEL: str = field(default_factory=lambda: _str("LOG_LEVEL", "INFO"))
    TESTING: bool = False

    @property
    def is_production(self) -> bool:
        return self.FLASK_ENV.lower() == "production"

    @property
    def cookie_secure(self) -> bool:
        return self.COOKIE_SECURE if self.COOKIE_SECURE is not None else self.is_production

    @property
    def single_user(self) -> bool:
        return bool(self.APP_USER_EMAIL)

    def validate(self) -> None:
        """Fail fast on unsafe production configuration."""
        if self.SESSION_TTL_HOURS < 1:
            # 0 would expire every session immediately (login appears to work, then bounces back).
            import logging

            logging.getLogger(__name__).warning("SESSION_TTL_HOURS must be at least 1; using 12")
            self.SESSION_TTL_HOURS = 12
        if self.REMEMBER_TTL_DAYS < 1:
            self.REMEMBER_TTL_DAYS = 30
        if self.APP_USER_EMAIL and len(self.APP_USER_PASSWORD) < 8:
            raise RuntimeError("APP_USER_PASSWORD must be set and at least 8 characters when APP_USER_EMAIL is set")
        if not self.is_production:
            if not self.SECRET_KEY:
                self.SECRET_KEY = "dev-only-secret-key-change-me"
            if not self.SESSION_SECRET:
                self.SESSION_SECRET = "dev-only-session-secret-change-me"
            return
        missing = [name for name in ("SECRET_KEY", "SESSION_SECRET", "MONGODB_URI") if not getattr(self, name)]
        if missing:
            raise RuntimeError(f"Missing required production settings: {', '.join(missing)}")
        if len(self.SESSION_SECRET) < 32:
            raise RuntimeError("SESSION_SECRET must be at least 32 characters in production")
