from conftest import PASSWORD, ApiClient, data


def test_login_sets_httponly_cookie_and_returns_csrf(app, user):
    client = app.test_client()
    response = client.post("/api/auth/login", json={"email": "DEMO@example.com", "password": PASSWORD})
    assert response.status_code == 200
    body = data(response)
    assert body["user"]["email"] == "demo@example.com"
    assert body["csrf_token"]
    cookie = response.headers["Set-Cookie"]
    assert "worklog_session=" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert "Max-Age" not in cookie  # browser-session cookie without "remember me"


def test_remember_me_sets_persistent_cookie(app, user):
    response = app.test_client().post("/api/auth/login", json={"email": user["email"], "password": PASSWORD, "remember": True})
    assert "Max-Age=2592000" in response.headers["Set-Cookie"]


def test_password_is_hashed(services, user):
    stored = services.repos.users.by_email(user["email"])
    assert stored["password_hash"] != PASSWORD
    assert stored["password_hash"].startswith("$2")


def test_invalid_credentials(app, user):
    client = app.test_client()
    for email, password in ((user["email"], "wrong-password"), ("nobody@example.com", PASSWORD)):
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 401
        assert response.get_json()["error"]["code"] == "INVALID_CREDENTIALS"
        assert response.get_json()["error"]["message"] == "Invalid email or password."


def test_login_validation(app):
    client = app.test_client()
    response = client.post("/api/auth/login", json={"email": "not-an-email", "password": ""})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"
    response = client.post("/api/auth/login", data="email=x", content_type="application/x-www-form-urlencoded")
    assert response.status_code == 400


def test_login_rate_limited(app, user):
    client = app.test_client()
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": user["email"], "password": "nope-nope"}).status_code == 401
    response = client.post("/api/auth/login", json={"email": user["email"], "password": PASSWORD})
    assert response.status_code == 429
    assert response.get_json()["error"]["code"] == "RATE_LIMITED"


def test_smtp_auth_errors_explain_the_server_reason():
    import smtplib

    from app.services.email_service import _auth_error_message

    disabled = smtplib.SMTPAuthenticationError(535, b"5.7.139 Authentication unsuccessful, SmtpClientAuthentication is disabled for the Tenant. [X]")
    assert "SMTP AUTH" in _auth_error_message(disabled) and "IT" in _auth_error_message(disabled)
    wrong = smtplib.SMTPAuthenticationError(535, b"5.7.3 Authentication unsuccessful [ABC]")
    assert _auth_error_message(wrong) == "SMTP authentication failed (535): 5.7.3 Authentication unsuccessful"


def test_rate_limit_can_be_disabled():
    from app.utils.security import LoginRateLimiter

    limiter = LoginRateLimiter(max_attempts=0)
    for _ in range(50):
        limiter.record_failure("a@b.com", "1.2.3.4")
    assert limiter.retry_after("a@b.com", "1.2.3.4") == 0


def test_protected_routes_require_auth(app):
    client = app.test_client()
    for url in ("/api/auth/me", "/api/dashboard", "/api/calendar", "/api/work-logs/2026-10-03", "/api/projects",
                "/api/history/work", "/api/history/eod", "/api/settings", "/api/eod/2026-10-03"):
        response = client.get(url)
        assert response.status_code == 401, url
        assert response.get_json() == {"success": False, "error": {"code": "UNAUTHORIZED", "message": "Please sign in to continue."}}


def test_me_and_logout(api: ApiClient):
    me = data(api.get("/api/auth/me"))
    assert me["user"]["name"] == "Janakiraman"
    assert me["csrf_token"] == api.csrf
    assert data(api.post("/api/auth/logout"))["logged_out"] is True
    assert api.get("/api/auth/me").status_code == 401


def test_mutations_require_csrf_token(api: ApiClient):
    response = api.client.post("/api/projects", json={"name": "No CSRF"})
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "CSRF_FAILED"
    response = api.client.post("/api/projects", json={"name": "Bad CSRF"}, headers={"X-CSRF-Token": "forged"})
    assert response.status_code == 403
    assert api.post("/api/projects", {"name": "With CSRF"}).status_code == 201


def test_session_token_not_stored_in_plaintext(app, services, user):
    client = app.test_client()
    response = client.post("/api/auth/login", json={"email": user["email"], "password": PASSWORD})
    token = response.headers["Set-Cookie"].split("worklog_session=")[1].split(";")[0]
    assert services.repos.sessions.col.count_documents({"token_hash": token}) == 0
    assert services.repos.sessions.col.count_documents({}) == 1


def test_errors_do_not_leak_internals(app):
    response = app.test_client().get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"
