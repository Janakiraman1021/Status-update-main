"""Password hashing, session tokens and login rate limiting."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

import bcrypt

_BCRYPT_ROUNDS = 12
# Pre-computed hash used to keep timing constant when the email does not exist.
_DUMMY_HASH = bcrypt.hashpw(b"worklog-dummy-password", bcrypt.gensalt(rounds=_BCRYPT_ROUNDS))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH)
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str, secret: str) -> str:
    """Session tokens are stored as keyed hashes so a database leak does not expose live sessions."""
    return hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


def constant_time_equals(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


class LoginRateLimiter:
    """Sliding-window limiter for failed logins (per process).

    Keyed by email+IP so one attacker cannot lock out every user behind a shared proxy,
    with a looser per-IP ceiling to slow credential stuffing.
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 900, ip_multiplier: int = 4):
        self.max_attempts = max_attempts
        self.window = window_seconds
        self.ip_max = max_attempts * ip_multiplier
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        events = self._events[key]
        while events and now - events[0] > self.window:
            events.popleft()
        return events

    @property
    def enabled(self) -> bool:
        return self.max_attempts > 0

    def retry_after(self, email: str, ip: str) -> int:
        """Seconds until another attempt is allowed (0 when allowed or when limiting is disabled)."""
        if not self.enabled:
            return 0
        now = time.monotonic()
        with self._lock:
            waits = []
            for key, limit in ((f"e:{email}|{ip}", self.max_attempts), (f"i:{ip}", self.ip_max)):
                events = self._prune(key, now)
                if len(events) >= limit:
                    waits.append(int(self.window - (now - events[0])) + 1)
            return max(waits) if waits else 0

    def record_failure(self, email: str, ip: str) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        with self._lock:
            self._events[f"e:{email}|{ip}"].append(now)
            self._events[f"i:{ip}"].append(now)

    def reset(self, email: str, ip: str) -> None:
        with self._lock:
            self._events.pop(f"e:{email}|{ip}", None)
