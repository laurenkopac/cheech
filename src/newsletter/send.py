"""
Sends the drafted newsletter (see summarize.py) via Gmail SMTP.

Pure transport -- rendering the structured draft into HTML/plain-text lives
in render.py so it's testable without SMTP or an ANTHROPIC_API_KEY.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.newsletter.render import render_html, render_text


def send_newsletter(subject: str, data: dict):
    from_email = os.environ.get("NEWSLETTER_FROM_EMAIL")
    to_email = os.environ.get("NEWSLETTER_TO_EMAIL")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not all([from_email, to_email, app_password]):
        raise RuntimeError("Missing Gmail SMTP config in environment variables")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    # Plain-text part first, HTML second -- clients that support both use
    # the last (HTML) part, so this order is what makes the fallback a
    # fallback rather than the default.
    msg.attach(MIMEText(render_text(data), "plain"))
    msg.attach(MIMEText(render_html(data), "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(from_email, app_password)
        server.send_message(msg)
