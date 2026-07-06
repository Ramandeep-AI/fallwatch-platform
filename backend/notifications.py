"""Alert notification channels.

Channels activate from environment configuration. The console channel is
always active, so the alert pipeline works end-to-end with no external
accounts; setting SMTP_HOST (see .env.example) enables real emails. Further
channels (e.g. SMS) implement the same two-method interface.
"""
import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("fallwatch.alerts")


class ConsoleNotifier:
    """Writes alerts to the application log. Always active."""

    name = "console"

    def send(self, subject: str, body: str) -> None:
        logger.warning("ALERT | %s | %s", subject, body)


class EmailNotifier:
    """Sends alerts over SMTP. Active when fully configured."""

    name = "email"

    @staticmethod
    def is_configured() -> bool:
        return bool(os.environ.get("SMTP_HOST")
                    and os.environ.get("ALERT_EMAIL_TO"))

    def __init__(self):
        self.host = os.environ["SMTP_HOST"]
        self.port = int(os.environ.get("SMTP_PORT", "587"))
        self.user = os.environ.get("SMTP_USER", "")
        self.password = os.environ.get("SMTP_PASSWORD", "")
        self.to_addr = os.environ["ALERT_EMAIL_TO"]

    def send(self, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.user or "fallwatch@localhost"
        msg["To"] = self.to_addr
        msg.set_content(body)
        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            smtp.starttls()
            if self.user:
                smtp.login(self.user, self.password)
            smtp.send_message(msg)
        logger.info("alert email sent to %s", self.to_addr)


def configured_channels() -> list[str]:
    """Channel names only - safe to call from the request path, cannot fail
    on partial configuration (a half-configured channel is skipped and
    logged rather than turning ingestion into a 500)."""
    channels = [ConsoleNotifier.name]
    if EmailNotifier.is_configured():
        channels.append(EmailNotifier.name)
    elif os.environ.get("SMTP_HOST"):
        logger.warning("SMTP_HOST set but ALERT_EMAIL_TO missing - "
                       "email channel disabled")
    return channels


def active_notifiers():
    notifiers = [ConsoleNotifier()]
    if EmailNotifier.is_configured():
        notifiers.append(EmailNotifier())
    return notifiers


def dispatch(subject: str, body: str) -> None:
    """Send through every active channel; one failing channel must not
    block the others."""
    for notifier in active_notifiers():
        try:
            notifier.send(subject, body)
        except Exception:
            logger.exception("alert delivery failed on channel '%s'",
                             notifier.name)
