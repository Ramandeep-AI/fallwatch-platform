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

import requests

logger = logging.getLogger("fallwatch.alerts")

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
EXPO_PUSH_BATCH = 100  # Expo's documented per-request message limit


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


class ExpoPushNotifier:
    """Sends alerts to registered mobile devices through Expo's push service.

    Tokens are passed in by the caller (they live in the database, and this
    module stays free of database access); the channel is active whenever at
    least one device has registered via POST /api/v1/push-tokens.
    """

    name = "push"

    def __init__(self, tokens):
        self.tokens = list(tokens)

    def send(self, subject: str, body: str) -> None:
        for start in range(0, len(self.tokens), EXPO_PUSH_BATCH):
            chunk = self.tokens[start:start + EXPO_PUSH_BATCH]
            messages = [{
                "to": token,
                "title": subject,
                "body": body,
                "sound": "default",
                "priority": "high",
                "channelId": "fall-alerts",  # matches the mobile app's Android channel
            } for token in chunk]
            response = requests.post(EXPO_PUSH_URL, json=messages, timeout=10)
            response.raise_for_status()
            tickets = response.json().get("data", [])
            errors = [t for t in tickets if t.get("status") != "ok"]
            logger.info("push alert sent to %d device(s), %d rejected",
                        len(chunk) - len(errors), len(errors))
            for ticket in errors:
                logger.warning("push ticket error: %s", ticket)


def configured_channels(push_configured: bool = False) -> list[str]:
    """Channel names only - safe to call from the request path, cannot fail
    on partial configuration (a half-configured channel is skipped and
    logged rather than turning ingestion into a 500)."""
    channels = [ConsoleNotifier.name]
    if EmailNotifier.is_configured():
        channels.append(EmailNotifier.name)
    elif os.environ.get("SMTP_HOST"):
        logger.warning("SMTP_HOST set but ALERT_EMAIL_TO missing - "
                       "email channel disabled")
    if push_configured:
        channels.append(ExpoPushNotifier.name)
    return channels


def active_notifiers(push_tokens=()):
    notifiers = [ConsoleNotifier()]
    if EmailNotifier.is_configured():
        notifiers.append(EmailNotifier())
    if push_tokens:
        notifiers.append(ExpoPushNotifier(push_tokens))
    return notifiers


def dispatch(subject: str, body: str, push_tokens=()) -> None:
    """Send through every active channel; one failing channel must not
    block the others."""
    for notifier in active_notifiers(push_tokens):
        try:
            notifier.send(subject, body)
        except Exception:
            logger.exception("alert delivery failed on channel '%s'",
                             notifier.name)
