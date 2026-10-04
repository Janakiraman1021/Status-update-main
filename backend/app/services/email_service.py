"""Email delivery abstraction.

EMAIL_PROVIDER:
  smtp     real delivery through an SMTP server (Office 365, Gmail, SES, ...)
  console  development: writes each message to OUTBOX_DIR as an .eml file and logs it
  memory   tests: keeps messages in memory
Add Microsoft Graph or another provider by implementing EmailProvider.
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.message import EmailMessage as MimeMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

from ..repositories.email_repository import EmailLogRepository
from ..utils.datetime_utils import utcnow

logger = logging.getLogger(__name__)


class EmailError(Exception):
    pass


@dataclass
class OutgoingEmail:
    to: list[str]
    subject: str
    html: str
    text: str
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    reply_to: str | None = None
    # Images referenced from the HTML as src="cid:<cid>" (e.g. the company logo), sent inside the email.
    inline_images: list["InlineImage"] = field(default_factory=list)


@dataclass
class InlineImage:
    cid: str
    data: bytes
    mime_type: str  # e.g. "image/png"


@dataclass
class DeliveryResult:
    success: bool
    message_id: str | None = None
    error: str | None = None


def _auth_error_message(exc: smtplib.SMTPAuthenticationError) -> str:
    """Explain SMTP login failures using the server's own reason (never includes credentials)."""
    reply = exc.smtp_error.decode(errors="replace") if isinstance(exc.smtp_error, bytes) else str(exc.smtp_error)
    if "SmtpClientAuthentication is disabled" in reply:
        return ("Office 365 has SMTP sign-in (SMTP AUTH) disabled for this organisation, so the email could not be sent. "
                "Ask IT to enable Authenticated SMTP for your mailbox (https://aka.ms/smtp_auth_disabled).")
    reason = reply.split("[", 1)[0].strip()[:200]
    return f"SMTP authentication failed ({exc.smtp_code}): {reason}" if reason else "SMTP authentication failed. Check SMTP_USERNAME / SMTP_PASSWORD."


class EmailProvider(ABC):
    name = "base"

    def __init__(self, sender: str, sender_name: str):
        self.sender = sender
        self.sender_name = sender_name

    def build_mime(self, email: OutgoingEmail) -> MimeMessage:
        msg = MimeMessage()
        msg["From"] = formataddr((self.sender_name, self.sender)) if self.sender_name else self.sender
        msg["To"] = ", ".join(email.to)
        if email.cc:
            msg["Cc"] = ", ".join(email.cc)
        if email.reply_to:
            msg["Reply-To"] = email.reply_to
        msg["Subject"] = email.subject
        domain = self.sender.split("@")[-1] if "@" in self.sender else "worklog.local"
        msg["Message-ID"] = make_msgid(domain=domain)
        msg.set_content(email.text)
        msg.add_alternative(email.html, subtype="html")
        if email.inline_images:
            # multipart/related inside the HTML alternative, so clients show the logo without fetching anything.
            html_part = msg.get_payload()[-1]
            for image in email.inline_images:
                maintype, _, subtype = image.mime_type.partition("/")
                html_part.add_related(image.data, maintype=maintype, subtype=subtype, cid=f"<{image.cid}>",
                                      disposition="inline", filename=f"{image.cid}.{subtype.replace('jpeg', 'jpg')}")
        return msg

    @abstractmethod
    def send(self, email: OutgoingEmail) -> DeliveryResult: ...

    @abstractmethod
    def test_connection(self) -> DeliveryResult: ...

    def status(self) -> dict:
        return {"provider": self.name, "sender": self.sender, "configured": bool(self.sender)}


class SmtpProvider(EmailProvider):
    name = "smtp"

    def __init__(self, host: str, port: int, username: str, password: str, use_tls: bool, use_ssl: bool,
                 sender: str, sender_name: str, timeout: int = 30):
        super().__init__(sender or username, sender_name)
        self.host, self.port = host, port
        self.username, self._password = username, password
        self.use_tls, self.use_ssl, self.timeout = use_tls, use_ssl, timeout

    def _connect(self) -> smtplib.SMTP:
        if not self.host:
            raise EmailError("SMTP_HOST is not configured.")
        context = ssl.create_default_context()
        if self.use_ssl:
            server: smtplib.SMTP = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=context)
        else:
            server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
            server.ehlo()
            if self.use_tls:
                server.starttls(context=context)
                server.ehlo()
        if self.username:
            server.login(self.username, self._password)
        return server

    def send(self, email: OutgoingEmail) -> DeliveryResult:
        msg = self.build_mime(email)
        recipients = [*email.to, *email.cc, *email.bcc]
        try:
            with self._connect() as server:
                refused = server.send_message(msg, to_addrs=recipients)
            if refused and len(refused) == len(recipients):
                return DeliveryResult(False, error="All recipients were refused by the SMTP server.")
            return DeliveryResult(True, message_id=msg["Message-ID"])
        except smtplib.SMTPAuthenticationError as exc:
            return DeliveryResult(False, error=_auth_error_message(exc))
        except (smtplib.SMTPException, OSError, EmailError) as exc:
            return DeliveryResult(False, error=f"SMTP delivery failed: {exc.__class__.__name__}: {exc}"[:500])

    def test_connection(self) -> DeliveryResult:
        try:
            with self._connect() as server:
                server.noop()
            return DeliveryResult(True)
        except smtplib.SMTPAuthenticationError as exc:
            return DeliveryResult(False, error=_auth_error_message(exc))
        except (smtplib.SMTPException, OSError, EmailError) as exc:
            return DeliveryResult(False, error=f"Could not connect to SMTP server: {exc}"[:500])

    def status(self) -> dict:
        return {**super().status(), "host": self.host, "port": self.port, "tls": self.use_tls, "ssl": self.use_ssl,
                "configured": bool(self.host and self.sender)}


class ConsoleProvider(EmailProvider):
    """Development provider: the message is written to disk so it can be opened in any mail client."""

    name = "console"

    def __init__(self, outbox_dir: str, sender: str, sender_name: str):
        super().__init__(sender or "worklog@localhost", sender_name)
        self.outbox = Path(outbox_dir)

    def send(self, email: OutgoingEmail) -> DeliveryResult:
        msg = self.build_mime(email)
        self.outbox.mkdir(parents=True, exist_ok=True)
        stamp = utcnow().strftime("%Y%m%dT%H%M%S%f")
        path = self.outbox / f"{stamp}.eml"
        path.write_bytes(bytes(msg))
        logger.info("Email written to outbox", extra={"path": str(path), "to": email.to, "subject": email.subject})
        return DeliveryResult(True, message_id=msg["Message-ID"])

    def test_connection(self) -> DeliveryResult:
        try:
            self.outbox.mkdir(parents=True, exist_ok=True)
            return DeliveryResult(True) if os.access(self.outbox, os.W_OK) else DeliveryResult(False, error="Outbox is not writable.")
        except OSError as exc:
            return DeliveryResult(False, error=str(exc))

    def status(self) -> dict:
        return {**super().status(), "outbox": str(self.outbox.resolve()), "configured": True}


class MemoryProvider(EmailProvider):
    name = "memory"

    def __init__(self, sender: str = "worklog@test.local", sender_name: str = "WorkLog"):
        super().__init__(sender, sender_name)
        self.sent: list[OutgoingEmail] = []
        self.fail_with: str | None = None
        self._lock = threading.Lock()

    def send(self, email: OutgoingEmail) -> DeliveryResult:
        if self.fail_with:
            return DeliveryResult(False, error=self.fail_with)
        with self._lock:
            self.sent.append(email)
        return DeliveryResult(True, message_id=f"<memory-{len(self.sent)}@test.local>")

    def test_connection(self) -> DeliveryResult:
        return DeliveryResult(not self.fail_with, error=self.fail_with)


_PR_ATTACH_CONTENT_ID = "http://schemas.microsoft.com/mapi/proptag/0x3712001F"
_PR_ATTACHMENT_HIDDEN = "http://schemas.microsoft.com/mapi/proptag/0x7FFE000B"


class OutlookProvider(EmailProvider):
    """Sends through the Outlook (classic) desktop app signed in on this Windows PC.

    Outlook delivers the message with its own connection to Exchange/Microsoft 365, so organisation
    policies that block SMTP AUTH do not apply, and the email appears in the user's Sent Items.
    The backend must run on the same Windows machine, under the same user, as Outlook.
    """

    name = "outlook"

    def __init__(self, sender: str = "", sender_name: str = ""):
        super().__init__(sender, sender_name)
        self._lock = threading.Lock()

    @staticmethod
    def _com():
        try:
            import pythoncom  # noqa: F401
            import win32com.client  # noqa: F401
        except ImportError as exc:  # non-Windows, or pywin32 not installed
            raise EmailError("Outlook sending needs Windows with Outlook (classic) and the pywin32 package.") from exc
        import pythoncom
        import win32com.client

        return pythoncom, win32com.client

    def _account(self, namespace):
        """The Outlook account matching EMAIL_FROM, or None to use Outlook's default account."""
        if not self.sender:
            return None
        for account in namespace.Accounts:
            if str(account.SmtpAddress).lower() == self.sender.lower():
                return account
        raise EmailError(f"Outlook has no account for {self.sender}. Check EMAIL_FROM or add the account in Outlook.")

    def send(self, email: OutgoingEmail) -> DeliveryResult:
        try:
            pythoncom, client = self._com()
        except EmailError as exc:
            return DeliveryResult(False, error=str(exc))
        with self._lock:
            pythoncom.CoInitialize()  # each Flask/scheduler thread needs its own COM apartment
            temp_dir = None
            try:
                app = client.Dispatch("Outlook.Application")
                namespace = app.GetNamespace("MAPI")
                mail = app.CreateItem(0)  # olMailItem
                account = self._account(namespace)
                if account is not None:
                    mail._oleobj_.Invoke(*(64209, 0, 8, 0, account))  # SendUsingAccount
                mail.To = "; ".join(email.to)
                mail.CC = "; ".join(email.cc)
                mail.BCC = "; ".join(email.bcc)
                mail.Subject = email.subject
                if email.inline_images:
                    import tempfile

                    temp_dir = Path(tempfile.mkdtemp(prefix="worklog-"))
                    for image in email.inline_images:
                        ext = image.mime_type.split("/")[-1].replace("jpeg", "jpg")
                        path = temp_dir / f"{image.cid}.{ext}"
                        path.write_bytes(image.data)
                        attachment = mail.Attachments.Add(str(path))
                        attachment.PropertyAccessor.SetProperty(_PR_ATTACH_CONTENT_ID, image.cid)
                        attachment.PropertyAccessor.SetProperty(_PR_ATTACHMENT_HIDDEN, True)
                mail.HTMLBody = email.html
                mail.Send()
                return DeliveryResult(True, message_id="outlook")
            except EmailError as exc:
                return DeliveryResult(False, error=str(exc))
            except Exception as exc:  # COM errors carry Outlook's own description
                detail = getattr(exc, "excepinfo", None)
                message = detail[2] if detail and len(detail) > 2 and detail[2] else str(exc)
                return DeliveryResult(False, error=f"Outlook could not send the email: {message}"[:500])
            finally:
                if temp_dir:
                    for file in temp_dir.iterdir():
                        file.unlink(missing_ok=True)
                    temp_dir.rmdir()
                pythoncom.CoUninitialize()

    def test_connection(self) -> DeliveryResult:
        try:
            pythoncom, client = self._com()
        except EmailError as exc:
            return DeliveryResult(False, error=str(exc))
        with self._lock:
            pythoncom.CoInitialize()
            try:
                namespace = client.Dispatch("Outlook.Application").GetNamespace("MAPI")
                self._account(namespace)
                return DeliveryResult(True)
            except EmailError as exc:
                return DeliveryResult(False, error=str(exc))
            except Exception as exc:
                return DeliveryResult(False, error=f"Could not open Outlook: {exc}"[:500])
            finally:
                pythoncom.CoUninitialize()

    def status(self) -> dict:
        return {**super().status(), "configured": True, "via": "Outlook (classic) on this PC"}


def create_email_provider(settings) -> EmailProvider:
    name = settings.EMAIL_PROVIDER
    if name == "outlook":
        return OutlookProvider(settings.EMAIL_FROM, settings.EMAIL_FROM_NAME)
    if name == "smtp":
        return SmtpProvider(
            settings.SMTP_HOST, settings.SMTP_PORT, settings.SMTP_USERNAME, settings.SMTP_PASSWORD,
            settings.SMTP_USE_TLS, settings.SMTP_USE_SSL, settings.EMAIL_FROM, settings.EMAIL_FROM_NAME,
            settings.SMTP_TIMEOUT_SECONDS,
        )
    if name == "console":
        return ConsoleProvider(settings.OUTBOX_DIR, settings.EMAIL_FROM, settings.EMAIL_FROM_NAME)
    if name == "memory":
        return MemoryProvider()
    raise RuntimeError(f"Unsupported EMAIL_PROVIDER '{name}'. Supported: outlook, smtp, console, memory")


class EmailService:
    """Sends mail through the configured provider and records every attempt in email_logs."""

    def __init__(self, provider: EmailProvider, logs: EmailLogRepository):
        self.provider = provider
        self.logs = logs

    def send_email(self, email: OutgoingEmail, user_id=None, kind: str = "generic", reference: dict | None = None) -> DeliveryResult:
        if not email.to:
            return DeliveryResult(False, error="At least one recipient is required.")
        try:
            result = self.provider.send(email)
        except Exception as exc:  # provider bugs must never lose the audit trail
            logger.exception("Email provider raised unexpectedly")
            result = DeliveryResult(False, error=f"Unexpected email error: {exc.__class__.__name__}")
        self.logs.record(user_id, kind, email.to, email.cc, email.bcc, email.subject, self.provider.name,
                         result.success, result.message_id, result.error, reference)
        log = logger.info if result.success else logger.warning
        log("Email send attempt", extra={"kind": kind, "provider": self.provider.name, "success": result.success,
                                          "to_count": len(email.to) + len(email.cc) + len(email.bcc), "error": result.error})
        return result

    def send_eod(self, *, user_id, eod_id, version: int, to: list[str], cc: list[str], bcc: list[str],
                 subject: str, html_body: str, text_body: str, reply_to: str | None,
                 inline_images: list[InlineImage] | None = None) -> DeliveryResult:
        email = OutgoingEmail(to=to, cc=cc, bcc=bcc, subject=subject, html=html_body, text=text_body, reply_to=reply_to,
                              inline_images=inline_images or [])
        return self.send_email(email, user_id=user_id, kind="eod", reference={"eod_id": eod_id, "version": version})

    def test_connection(self) -> DeliveryResult:
        return self.provider.test_connection()

    def status(self) -> dict:
        return self.provider.status()
