from __future__ import annotations

import os
import uuid

import mongomock
import pytest
from pymongo import MongoClient

from app import create_app
from app.config import Settings
from app.services import EXTENSION_KEY
from app.services.ai_service import LocalProvider
from app.services.email_service import MemoryProvider

PASSWORD = "Correct-Horse-9"


def make_settings(**overrides) -> Settings:
    settings = Settings()
    settings.FLASK_ENV = "testing"
    settings.TESTING = True
    settings.MONGODB_URI = "mongomock://"
    settings.MONGODB_DATABASE = "worklog_test"
    settings.SECRET_KEY = "test-secret"
    settings.SESSION_SECRET = "test-session-secret-which-is-long-enough"
    settings.AI_PROVIDER = "local"
    settings.EMAIL_PROVIDER = "memory"
    settings.DEFAULT_TIMEZONE = "Asia/Kolkata"
    settings.EOD_DEFAULT_TIME = "18:30"
    settings.SCHEDULER_ENABLED = False
    settings.LOG_LEVEL = "WARNING"
    settings.APP_USER_EMAIL = ""  # tests create their own users unless a test opts into single-user mode
    settings.APP_USER_PASSWORD = ""
    settings.SESSION_TTL_HOURS = 12
    settings.REMEMBER_TTL_DAYS = 30
    settings.COOKIE_SECURE = None
    settings.LOGIN_MAX_ATTEMPTS = 5
    settings.LOGIN_WINDOW_SECONDS = 900
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


@pytest.fixture
def mail() -> MemoryProvider:
    return MemoryProvider()


@pytest.fixture
def ai():
    return LocalProvider()


@pytest.fixture
def app(mail, ai):
    """Uses an in-memory mongomock database, or a real server when TEST_MONGODB_URI is set
    (each test gets its own throwaway database)."""
    real_uri = os.getenv("TEST_MONGODB_URI")
    database = f"worklog_test_{uuid.uuid4().hex[:12]}" if real_uri else "worklog_test"
    client = MongoClient(real_uri, tz_aware=True) if real_uri else mongomock.MongoClient(tz_aware=True)
    application = create_app(make_settings(MONGODB_DATABASE=database), mongo_client=client, ai_provider=ai,
                             email_provider=mail, start_scheduler=False)
    yield application
    if real_uri:
        client.drop_database(database)
        client.close()


@pytest.fixture
def services(app):
    from app.db import get_db
    from app.services import build_services

    with app.app_context():
        yield build_services(get_db(), app.config["SETTINGS"], app.extensions[EXTENSION_KEY])


class ApiClient:
    """Test client that logs in and attaches the CSRF header like the real frontend."""

    def __init__(self, flask_client):
        self.client = flask_client
        self.csrf: str | None = None

    def login(self, email: str, password: str = PASSWORD, remember: bool = False):
        response = self.client.post("/api/auth/login", json={"email": email, "password": password, "remember": remember})
        if response.status_code == 200:
            self.csrf = response.get_json()["data"]["csrf_token"]
        return response

    def _headers(self):
        return {"X-CSRF-Token": self.csrf} if self.csrf else {}

    def get(self, url, **kwargs):
        return self.client.get(url, **kwargs)

    def post(self, url, json=None, **kwargs):
        return self.client.post(url, json=json if json is not None else {}, headers=self._headers(), **kwargs)

    def put(self, url, json=None, **kwargs):
        return self.client.put(url, json=json or {}, headers=self._headers(), **kwargs)

    def delete(self, url, **kwargs):
        return self.client.delete(url, headers=self._headers(), **kwargs)


def data(response):
    body = response.get_json()
    assert body["success"] is True, body
    return body["data"]


@pytest.fixture
def make_user(services):
    def _make(email="demo@example.com", name="Janakiraman", password=PASSWORD):
        return services.auth.create_user(name, email, password)

    return _make


@pytest.fixture
def user(make_user):
    return make_user()


@pytest.fixture
def api(app, user) -> ApiClient:
    client = ApiClient(app.test_client())
    assert client.login(user["email"]).status_code == 200
    return client


@pytest.fixture
def other_api(app, make_user) -> ApiClient:
    other = make_user("other@example.com", "Other User")
    client = ApiClient(app.test_client())
    assert client.login(other["email"]).status_code == 200
    return client


@pytest.fixture
def today(services, user):
    from app.utils.datetime_utils import local_today

    return local_today(services.settings.timezone(user["_id"]))
