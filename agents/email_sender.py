import os
import smtplib
from email.message import EmailMessage
from typing import Optional

GMAIL_SMTP_SERVER = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465
RECIPIENT_EMAIL = "sdtyree2001@gmail.com"
SENDER_ENV = "GMAIL_SENDER"
PASSWORD_ENV = "GMAIL_APP_PASSWORD"


def _get_credentials() -> tuple[str, str]:
    """Load Gmail credentials from environment variables."""
    sender = os.environ.get(SENDER_ENV, "")
    password = os.environ.get(PASSWORD_ENV, "")
    return sender, password


def _build_message(subject: str, html_body: str, x_priority: Optional[str] = None) -> EmailMessage:
    """Build the email message object for Gmail SMTP."""
    sender, _ = _get_credentials()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = RECIPIENT_EMAIL
    message.set_content("Pulse email requires an HTML-capable client.")
    message.add_alternative(html_body, subtype="html")
    if x_priority:
        message["X-Priority"] = x_priority
    return message


def send_daily_brief(html_body: str, run_date: str | None = None) -> bool:
    """Send the daily brief email via Gmail SMTP."""
    sender, password = _get_credentials()
    if not sender or not password:
        print("ERROR: Gmail sender credentials are missing.")
        return False

    subject_date = run_date or "Daily Brief"
    subject = f"Pulse Daily Brief — {subject_date}"
    message = _build_message(subject, html_body, x_priority="3")

    try:
        with smtplib.SMTP_SSL(GMAIL_SMTP_SERVER, GMAIL_SMTP_PORT, timeout=20) as smtp:
            smtp.login(sender, password)
            smtp.send_message(message)
        print("INFO: Daily brief sent successfully.")
        return True
    except smtplib.SMTPAuthenticationError:
        print("ERROR: Gmail authentication failed. Check GMAIL_SENDER and GMAIL_APP_PASSWORD.")
        return False
    except Exception as exc:
        print(f"ERROR: Email send failed: {exc}")
        return False


def send_alert_email(subject: str, html_body: str, priority: str = "high") -> bool:
    """Send a breaking news alert email via Gmail SMTP."""
    sender, password = _get_credentials()
    if not sender or not password:
        print("ERROR: Gmail sender credentials are missing.")
        return False

    x_priority = "1" if priority in {"critical", "high"} else "3"
    message = _build_message(subject, html_body, x_priority=x_priority)

    try:
        with smtplib.SMTP_SSL(GMAIL_SMTP_SERVER, GMAIL_SMTP_PORT, timeout=20) as smtp:
            smtp.login(sender, password)
            smtp.send_message(message)
        print(f"INFO: Alert email sent successfully with priority {priority}.")
        return True
    except smtplib.SMTPAuthenticationError:
        print("ERROR: Gmail authentication failed. Check GMAIL_SENDER and GMAIL_APP_PASSWORD.")
        return False
    except Exception as exc:
        print(f"ERROR: Alert email send failed: {exc}")
        return False
