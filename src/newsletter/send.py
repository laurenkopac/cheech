"""
Sends the drafted newsletter via Gmail SMTP.
"""
import os
import smtplib
from email.mime.text import MIMEText


def send_newsletter(subject: str, body_text: str):
    from_email = os.environ.get("NEWSLETTER_FROM_EMAIL")
    to_email = os.environ.get("NEWSLETTER_TO_EMAIL")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not all([from_email, to_email, app_password]):
        raise RuntimeError("Missing Gmail SMTP config in environment variables")

    msg = MIMEText(body_text)
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(from_email, app_password)
        server.send_message(msg)
