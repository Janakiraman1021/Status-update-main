"""Outlook (classic) provider, exercised against a fake Outlook COM object (no real mail is sent)."""
import sys
import types

import pytest

from app.services.email_service import InlineImage, OutgoingEmail, OutlookProvider, create_email_provider
from conftest import make_settings


class FakeProps:
    def __init__(self):
        self.values = {}

    def SetProperty(self, name, value):
        self.values[name] = value


class FakeAttachment:
    def __init__(self, path):
        self.path = path
        self.PropertyAccessor = FakeProps()


class FakeAttachments(list):
    def Add(self, path):
        attachment = FakeAttachment(path)
        self.append(attachment)
        return attachment


class FakeMail:
    def __init__(self, outbox):
        self.outbox = outbox
        self.Attachments = FakeAttachments()
        self._oleobj_ = types.SimpleNamespace(Invoke=lambda *args: setattr(self, "account_set", True))

    def Send(self):
        if self.outbox.get("fail"):
            raise RuntimeError("Outlook is offline")
        self.outbox["sent"].append(self)


class FakeOutlook:
    def __init__(self, outbox, accounts):
        self.outbox = outbox
        self.accounts = [types.SimpleNamespace(SmtpAddress=a) for a in accounts]

    def GetNamespace(self, _name):
        return types.SimpleNamespace(Accounts=self.accounts)

    def CreateItem(self, _kind):
        return FakeMail(self.outbox)


@pytest.fixture
def outlook(monkeypatch):
    outbox = {"sent": [], "fail": False, "accounts": ["janakiraman.k@samunnati.com"]}
    client = types.ModuleType("win32com.client")
    client.Dispatch = lambda name: FakeOutlook(outbox, outbox["accounts"])
    win32com = types.ModuleType("win32com")
    win32com.client = client
    pythoncom = types.ModuleType("pythoncom")
    pythoncom.CoInitialize = lambda: None
    pythoncom.CoUninitialize = lambda: None
    monkeypatch.setitem(sys.modules, "win32com", win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", client)
    monkeypatch.setitem(sys.modules, "pythoncom", pythoncom)
    return outbox


def _email(**overrides):
    base = dict(to=["manager@samunnati.com"], cc=["lead@samunnati.com"], bcc=[], subject="EOD Status Update | 03 Oct 2026",
                html="<p>Hi</p><img src=\"cid:brand-logo\">", text="Hi",
                inline_images=[InlineImage("brand-logo", b"\x89PNG", "image/png")])
    return OutgoingEmail(**{**base, **overrides})


def test_outlook_sends_with_fields_and_inline_logo(outlook):
    result = OutlookProvider("janakiraman.k@samunnati.com", "Janakiraman K").send(_email())
    assert result.success
    mail = outlook["sent"][0]
    assert mail.To == "manager@samunnati.com" and mail.CC == "lead@samunnati.com" and mail.BCC == ""
    assert mail.Subject == "EOD Status Update | 03 Oct 2026" and "cid:brand-logo" in mail.HTMLBody
    assert getattr(mail, "account_set", False)  # sent from the configured account
    props = mail.Attachments[0].PropertyAccessor.values
    assert "brand-logo" in props.values() and True in props.values()  # content-id + hidden


def test_outlook_errors_are_reported(outlook):
    outlook["fail"] = True
    result = OutlookProvider("janakiraman.k@samunnati.com").send(_email(inline_images=[]))
    assert not result.success and "Outlook could not send the email" in result.error


def test_outlook_unknown_sender_account(outlook):
    result = OutlookProvider("someone.else@samunnati.com").send(_email(inline_images=[]))
    assert not result.success and "no account for someone.else@samunnati.com" in result.error
    assert not OutlookProvider("someone.else@samunnati.com").test_connection().success
    assert OutlookProvider("janakiraman.k@samunnati.com").test_connection().success


def test_factory_creates_outlook_provider():
    provider = create_email_provider(make_settings(EMAIL_PROVIDER="outlook", EMAIL_FROM="janakiraman.k@samunnati.com"))
    assert provider.name == "outlook" and provider.status()["configured"] is True
