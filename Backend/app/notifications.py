
import logging
import os
import smtplib
from email.message import EmailMessage

import httpx

from . import config  # noqa: F401  (loads Backend/.env)

logger = logging.getLogger(__name__)


def send_telegram(text: str) -> bool:
    """Send a message through the Telegram Bot API."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        logger.info("Telegram notifications are not configured.")
        return False

    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
            },
            timeout=15,
        )
        response.raise_for_status()

        result = response.json()
        if not result.get("ok"):
            logger.error("Telegram API did not confirm message delivery.")
            return False

        logger.info("Telegram notification sent.")
        return True

    except (httpx.HTTPError, ValueError) as exc:
        logger.error("Failed to send Telegram notification (%s).", type(exc).__name__)
        return False


def send_email(subject: str, body: str) -> bool:
    """Send an email through an SMTP SSL server."""
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASS", "").strip()
    recipient = os.getenv("ALERT_TO", "").strip()

    if not all((host, user, password, recipient)):
        logger.info("Email notifications are not configured.")
        return False

    message = EmailMessage()
    message["From"] = user
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP_SSL(host, 465, timeout=20) as server:
            server.login(user, password)
            server.send_message(message)

        logger.info("Email notification sent to %s.", recipient)
        return True

    except (OSError, smtplib.SMTPException):
        logger.exception("Failed to send email notification.")
        return False


def notify(subject: str, body: str) -> dict:
    """Send a notification through every configured channel."""
    return {
        "telegram": send_telegram(f"{subject}\n{body}"),
        "email": send_email(subject, body),
    }
