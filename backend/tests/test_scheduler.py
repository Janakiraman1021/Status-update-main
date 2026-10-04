from datetime import datetime, timedelta, timezone

import pytest

from app.services.ai_service import AIError

DATE = "2026-10-03"
# 18:30 Asia/Kolkata == 13:00 UTC
BEFORE_EOD = datetime(2026, 10, 3, 12, 59, tzinfo=timezone.utc)
AT_EOD = datetime(2026, 10, 3, 13, 0, tzinfo=timezone.utc)
AFTER_EOD = datetime(2026, 10, 3, 13, 5, tzinfo=timezone.utc)


@pytest.fixture
def automated(services, user):
    services.settings.update(user, {"auto_eod_enabled": True, "eod_time": "18:30", "timezone": "Asia/Kolkata",
                                    "recipients": {"to": ["manager@example.com"], "cc": [], "bcc": []}})
    return user


def _log_work(services, user, date=DATE):
    services.work_logs.upsert(user["_id"], date, {"quick_notes": "removed selector\n94 tests passed"})


def test_does_nothing_before_eod_time(services, automated, mail):
    _log_work(services, automated)
    assert services.scheduler.run_tick(BEFORE_EOD) == {}
    assert mail.sent == []


def test_sends_at_eod_time(services, automated, mail):
    _log_work(services, automated)
    stats = services.scheduler.run_tick(AT_EOD)
    assert stats == {"auto_eod_sent": 1}
    report = services.repos.eods.by_date(automated["_id"], DATE)
    assert report["status"] == "SENT" and report["sent_by"] == "scheduler"
    assert mail.sent[0].to == ["manager@example.com"]
    version = services.repos.eod_versions.current(automated["_id"], report["_id"])
    assert version["created_by"] == "scheduler"


def test_scheduler_is_idempotent(services, automated, mail):
    _log_work(services, automated)
    services.scheduler.run_tick(AT_EOD)
    for minute in range(1, 30):
        services.scheduler.run_tick(AT_EOD + timedelta(minutes=minute))
    assert len(mail.sent) == 1
    assert services.repos.eods.col.count_documents({"user_id": automated["_id"]}) == 1


def test_scheduler_skips_manually_sent_eod(services, automated, mail):
    _log_work(services, automated)
    report = services.eod.generate(automated, DATE)
    services.eod.send(automated, report["_id"])
    assert services.scheduler.run_tick(AFTER_EOD) == {"skipped_already_sent": 1}
    assert len(mail.sent) == 1


def test_scheduler_sends_users_edited_version(services, automated, mail):
    _log_work(services, automated)
    report = services.eod.generate(automated, DATE)
    services.eod.update(automated, report["_id"], {"body": "Hi,\n\nMy hand-edited report.\n\nThanks and regards,\nJanakiraman"})
    services.scheduler.run_tick(AFTER_EOD)
    assert "hand-edited" in mail.sent[0].text
    assert services.repos.eod_versions.col.count_documents({"eod_id": report["_id"]}) == 2  # no regeneration


def test_scheduler_skips_when_no_work(services, automated, mail):
    assert services.scheduler.run_tick(AFTER_EOD) == {"skipped_no_work": 1}
    assert services.repos.eods.col.count_documents({}) == 0
    assert mail.sent == []


def test_disabled_automation_does_nothing(services, user, mail):
    services.settings.update(user, {"auto_eod_enabled": False})
    _log_work(services, user)
    assert services.scheduler.run_tick(AFTER_EOD) == {}


def test_email_failure_retries_with_backoff_and_limit(services, automated, mail):
    _log_work(services, automated)
    mail.fail_with = "SMTP down"
    assert services.scheduler.run_tick(AT_EOD) == {"auto_eod_failed": 1}
    assert services.scheduler.run_tick(AT_EOD + timedelta(minutes=5)) == {"skipped_not_due": 1}  # retry spacing
    services.scheduler.run_tick(AT_EOD + timedelta(minutes=11))
    services.scheduler.run_tick(AT_EOD + timedelta(minutes=22))
    assert services.scheduler.run_tick(AT_EOD + timedelta(minutes=40)) == {"skipped_not_due": 1}  # max 3 attempts
    report = services.repos.eods.by_date(automated["_id"], DATE)
    assert report["status"] == "FAILED" and report["auto_attempts"] == 3
    assert report["current_version"] == 1  # the report was generated once and reused for each retry


def test_failed_attempt_then_success(services, automated, mail):
    _log_work(services, automated)
    mail.fail_with = "SMTP down"
    services.scheduler.run_tick(AT_EOD)
    mail.fail_with = None
    assert services.scheduler.run_tick(AT_EOD + timedelta(minutes=11)) == {"auto_eod_sent": 1}
    assert len(mail.sent) == 1


def test_ai_failure_in_scheduler_keeps_work(services, automated, mail, monkeypatch):
    _log_work(services, automated)
    monkeypatch.setattr(services.eod.ai, "generate_eod", lambda c, style="standard": (_ for _ in ()).throw(AIError("down")))
    assert services.scheduler.run_tick(AT_EOD) == {"auto_eod_failed": 1}
    report = services.repos.eods.by_date(automated["_id"], DATE)
    assert report["status"] == "FAILED" and report["last_error"]["code"] == "EOD_GENERATION_FAILED"
    assert services.work_logs.has_work(automated["_id"], DATE)
    assert mail.sent == []


def test_concurrent_claims_only_one_wins(services, automated):
    _log_work(services, automated)
    repo = services.repos.eods
    first = repo.claim_auto_attempt(automated["_id"], DATE, AT_EOD, 3, timedelta(minutes=10))
    second = repo.claim_auto_attempt(automated["_id"], DATE, AT_EOD, 3, timedelta(minutes=10))
    assert first is not None and second is None


def test_send_claim_is_exclusive(services, automated):
    _log_work(services, automated)
    report = services.eod.generate(automated, DATE)
    assert services.repos.eods.claim_send(automated["_id"], report["_id"], False, AT_EOD) is not None
    assert services.repos.eods.claim_send(automated["_id"], report["_id"], False, AT_EOD) is None


def test_stale_sending_is_marked_unknown_and_not_retried(services, automated, mail):
    _log_work(services, automated)
    report = services.eod.generate(automated, DATE)
    services.repos.eods.claim_send(automated["_id"], report["_id"], False, AT_EOD - timedelta(minutes=30))
    services.scheduler.run_tick(AT_EOD)
    report = services.repos.eods.by_date(automated["_id"], DATE)
    assert report["status"] == "FAILED"
    assert report["last_error"]["code"] == "EMAIL_DELIVERY_UNKNOWN"
    services.scheduler.run_tick(AT_EOD + timedelta(minutes=30))
    assert mail.sent == []


def test_reminder_sent_once_when_no_work(services, user, mail):
    services.settings.update(user, {"reminder_enabled": True, "reminder_minutes_before": 30, "eod_time": "18:30"})
    assert services.scheduler.run_tick(datetime(2026, 10, 3, 12, 25, tzinfo=timezone.utc)) == {}  # 17:55 IST, too early
    assert services.scheduler.run_tick(datetime(2026, 10, 3, 12, 35, tzinfo=timezone.utc)) == {"reminder_sent": 1}
    services.scheduler.run_tick(datetime(2026, 10, 3, 12, 40, tzinfo=timezone.utc))
    assert len(mail.sent) == 1
    assert "haven't documented today's work" in mail.sent[0].text


def test_no_reminder_when_work_exists(services, user, mail):
    services.settings.update(user, {"reminder_enabled": True, "reminder_minutes_before": 30})
    _log_work(services, user)
    services.scheduler.run_tick(datetime(2026, 10, 3, 12, 45, tzinfo=timezone.utc))
    assert mail.sent == []


def test_scheduler_respects_each_users_timezone(services, automated, make_user, mail):
    london = make_user("london@example.com", "London User")
    services.settings.update(london, {"auto_eod_enabled": True, "eod_time": "18:30", "timezone": "Europe/London"})
    _log_work(services, automated)
    _log_work(services, london)
    services.scheduler.run_tick(AT_EOD)  # 18:30 in Kolkata, 14:00 in London
    assert [m.to for m in mail.sent] == [["manager@example.com"]]
    services.scheduler.run_tick(datetime(2026, 10, 3, 17, 30, tzinfo=timezone.utc))  # 18:30 BST
    assert len(mail.sent) == 2 and mail.sent[1].to == ["london@example.com"]
