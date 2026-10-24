import os
import smtplib
from email.message import EmailMessage
import httpx


def send_telegram(text: str):
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if tok and chat:
        httpx.post(f"https://api.telegram.org/bot{tok}/sendMessage", json={"chat_id": chat, "text": text})


def send_email(subject: str, body: str):
    host, user, pw, to = (os.getenv(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "ALERT_TO"))
    if not (host and user and pw and to):
        return
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = user, to, subject
    m.set_content(body)
    with smtplib.SMTP_SSL(host, 465) as s:
        s.login(user, pw)
        s.send_message(m)


def notify(subject: str, body: str):
    send_telegram(f"{subject}\n{body}")
    send_email(subject, body)