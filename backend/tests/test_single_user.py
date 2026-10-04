import mongomock
import pytest

from app import create_app
from app.services.ai_service import LocalProvider
from app.services.email_service import MemoryProvider
from conftest import make_settings

EMAIL = "me@company.com"
PASSWORD = "First-Password-1"


def _app(client, **overrides):
    settings = make_settings(**{"APP_USER_EMAIL": EMAIL, "APP_USER_PASSWORD": PASSWORD, "APP_USER_NAME": "Janakiraman", **overrides})
    return create_app(settings, mongo_client=client, ai_provider=LocalProvider(), email_provider=MemoryProvider(), start_scheduler=False)


def _login(app, email=EMAIL, password=PASSWORD):
    return app.test_client().post("/api/auth/login", json={"email": email, "password": password})


def test_env_user_is_created_and_can_sign_in():
    client = mongomock.MongoClient(tz_aware=True)
    app = _app(client)
    stored = client["worklog_test"].users.find_one({"email": EMAIL})
    assert stored["name"] == "Janakiraman"
    assert stored["password_hash"] != PASSWORD and stored["password_hash"].startswith("$2")
    response = _login(app)
    assert response.status_code == 200
    assert response.get_json()["data"]["user"]["email"] == EMAIL


def test_only_the_env_user_can_sign_in():
    client = mongomock.MongoClient(tz_aware=True)
    app = _app(client)
    with app.app_context():
        from app.db import get_db
        from app.services import EXTENSION_KEY, build_services
        build_services(get_db(), app.config["SETTINGS"], app.extensions[EXTENSION_KEY]).auth.create_user("Other", "other@company.com", "Other-Password-1")
    response = _login(app, "other@company.com", "Other-Password-1")
    assert response.status_code == 401
    assert response.get_json()["error"]["message"] == "Invalid email or password."
    assert _login(app, EMAIL, "wrong-password").status_code == 401


def test_changing_password_in_env_rotates_it_and_ends_sessions():
    client = mongomock.MongoClient(tz_aware=True)
    app = _app(client)
    browser = app.test_client()
    assert browser.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 200
    assert browser.get("/api/auth/me").status_code == 200

    restarted = _app(client, APP_USER_PASSWORD="Second-Password-2")
    assert _login(restarted, EMAIL, PASSWORD).status_code == 401
    assert _login(restarted, EMAIL, "Second-Password-2").status_code == 200
    assert client["worklog_test"].users.count_documents({}) == 1
    # The old browser session was revoked by the password change
    old_cookie = browser.get_cookie("worklog_session").value
    fresh = restarted.test_client()
    fresh.set_cookie("worklog_session", old_cookie)
    assert fresh.get("/api/auth/me").status_code == 401


def test_changing_email_keeps_the_existing_account_and_data():
    client = mongomock.MongoClient(tz_aware=True)
    _app(client)
    original_id = client["worklog_test"].users.find_one({"email": EMAIL})["_id"]
    restarted = _app(client, APP_USER_EMAIL="new@company.com")
    assert client["worklog_test"].users.count_documents({}) == 1
    assert client["worklog_test"].users.find_one({"_id": original_id})["email"] == "new@company.com"
    assert _login(restarted, "new@company.com", PASSWORD).status_code == 200


def test_restart_without_changes_keeps_hash():
    client = mongomock.MongoClient(tz_aware=True)
    _app(client)
    first = client["worklog_test"].users.find_one({"email": EMAIL})["password_hash"]
    _app(client)
    assert client["worklog_test"].users.find_one({"email": EMAIL})["password_hash"] == first


def test_short_password_is_rejected_at_startup():
    with pytest.raises(RuntimeError, match="APP_USER_PASSWORD"):
        _app(mongomock.MongoClient(tz_aware=True), APP_USER_PASSWORD="short")
