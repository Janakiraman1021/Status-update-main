from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from pymongo.errors import DuplicateKeyError

from ..repositories import Repositories
from ..utils.datetime_utils import utcnow
from ..utils.errors import Conflict, RateLimited, Unauthorized, ValidationFailed
from ..utils.security import LoginRateLimiter, hash_password, hash_token, new_token, verify_password

logger = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH = 8


@dataclass
class LoginResult:
    user: dict
    token: str
    csrf_token: str
    expires_at: datetime
    remember: bool


class AuthService:
    def __init__(self, repos: Repositories, config, limiter: LoginRateLimiter):
        self.repos = repos
        self.config = config
        self.limiter = limiter

    def _hash(self, token: str) -> str:
        return hash_token(token, self.config.SESSION_SECRET)

    def login(self, email: str, password: str, remember: bool, ip: str, user_agent: str | None) -> LoginResult:
        email = email.strip().lower()
        wait = self.limiter.retry_after(email, ip)
        if wait:
            logger.warning("Login rate limited", extra={"event": "auth.rate_limited", "ip": ip})
            raise RateLimited(f"Too many failed sign-in attempts. Try again in {max(1, wait // 60)} minute(s).", details={"retry_after": wait})

        user = self.repos.users.by_email(email)
        if self.config.single_user and email != self.config.APP_USER_EMAIL:
            user = None  # only the configured account may sign in (verify still runs, so timing is unchanged)
        if not verify_password(password, user.get("password_hash") if user and user.get("is_active", True) else None):
            self.limiter.record_failure(email, ip)
            logger.info("Login failed", extra={"event": "auth.login_failed", "ip": ip})
            raise Unauthorized("Invalid email or password.", code="INVALID_CREDENTIALS")

        self.limiter.reset(email, ip)
        now = utcnow()
        ttl = timedelta(days=self.config.REMEMBER_TTL_DAYS) if remember else timedelta(hours=self.config.SESSION_TTL_HOURS)
        token, csrf = new_token(), new_token(24)
        self.repos.sessions.create(user["_id"], self._hash(token), csrf, now + ttl, remember, user_agent)
        self.repos.users.touch_login(user["_id"], now)
        logger.info("Login succeeded", extra={"event": "auth.login", "user_id": str(user["_id"])})
        return LoginResult(user, token, csrf, now + ttl, remember)

    def resolve_session(self, token: str | None) -> tuple[dict, dict] | None:
        if not token:
            return None
        session = self.repos.sessions.active(self._hash(token))
        if not session:
            return None
        user = self.repos.users.by_id(session["user_id"])
        if not user:
            return None
        if self.config.single_user and user["email"] != self.config.APP_USER_EMAIL:
            return None
        return user, session

    def ensure_env_user(self) -> dict | None:
        """Single-user mode: make sure the account from APP_USER_* exists with the configured password and name.

        The database only ever stores the bcrypt hash; changing APP_USER_PASSWORD and restarting rotates it.
        """
        cfg = self.config
        if not cfg.single_user:
            return None
        user = self.repos.users.by_email(cfg.APP_USER_EMAIL)
        fields: dict = {}
        if not user:
            existing = list(self.repos.users.col.find({}).limit(2))
            if len(existing) == 1:
                # The login email changed: keep the existing account (and all its history) under the new email.
                user = existing[0]
                fields["email"] = cfg.APP_USER_EMAIL
            else:
                user = self.create_user(cfg.APP_USER_NAME, cfg.APP_USER_EMAIL, cfg.APP_USER_PASSWORD)
                logger.info("Single-user account created", extra={"event": "auth.env_user_created", "user_id": str(user["_id"])})
                return user
        if not verify_password(cfg.APP_USER_PASSWORD, user.get("password_hash")):
            fields["password_hash"] = hash_password(cfg.APP_USER_PASSWORD)
        if "password_hash" in fields or "email" in fields:
            # New credentials end all existing sessions.
            self.repos.sessions.col.delete_many({"user_id": user["_id"]})
        if user.get("is_active") is False:
            fields["is_active"] = True
        if fields:
            user = self.repos.users.update(user["_id"], fields)
            logger.info("Single-user account updated", extra={"event": "auth.env_user_updated",
                                                              "changed": sorted(k for k in fields if k != "password_hash") + (["password"] if "password_hash" in fields else [])})
        return user

    def logout(self, token: str | None) -> None:
        if token:
            self.repos.sessions.delete(self._hash(token))

    def create_user(self, name: str, email: str, password: str) -> dict:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValidationFailed(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
        if not name.strip():
            raise ValidationFailed("Name is required.")
        try:
            return self.repos.users.create(name, email, hash_password(password))
        except DuplicateKeyError as exc:
            raise Conflict("A user with this email already exists.", code="USER_EXISTS") from exc

    def set_password(self, user_id, password: str) -> None:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValidationFailed(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
        self.repos.users.update(user_id, {"password_hash": hash_password(password)})


def public_user(user: dict) -> dict:
    return {"id": user["_id"], "name": user["name"], "email": user["email"]}
