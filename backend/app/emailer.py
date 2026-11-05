"""Sending email (used for password reset links).

Works with any SMTP service. Free option: a Gmail address with an "app password"
(Google Account -> Security -> 2-Step Verification -> App passwords). Settings come
from environment variables, never from code:

    SMTP_HOST=smtp.gmail.com  SMTP_PORT=587  SMTP_USER=you@gmail.com
    SMTP_PASSWORD=<app password>  EMAIL_FROM="Card Tracker <you@gmail.com>"

If SMTP isn't set up (e.g. on your own computer), the email is printed to the server
log instead, so you can still click the link.
"""
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

log = logging.getLogger("card_tracker.email")


def is_configured() -> bool:
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER") and os.environ.get("SMTP_PASSWORD"))


def send_email(to: str, subject: str, text: str) -> None:
    if not is_configured():
        # Development fallback: nothing is sent; the message shows up in the terminal.
        print(f"\n--- Email (not sent, SMTP not set up) ---\nTo: {to}\nSubject: {subject}\n\n{text}\n---\n", flush=True)
        return
    message = EmailMessage()
    message["From"] = os.environ.get("EMAIL_FROM", os.environ["SMTP_USER"])
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    port = int(os.environ.get("SMTP_PORT", "587"))
    with smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=15) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(message)
