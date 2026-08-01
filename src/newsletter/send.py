"""
Sends the drafted newsletter via SendGrid (swap for plain SMTP if preferred).
"""
import os

import requests


def send_newsletter(subject: str, body_text: str):
    api_key = os.environ.get("SENDGRID_API_KEY")
    from_email = os.environ.get("NEWSLETTER_FROM_EMAIL")
    to_email = os.environ.get("NEWSLETTER_TO_EMAIL")

    if not all([api_key, from_email, to_email]):
        raise RuntimeError("Missing SendGrid config in environment variables")

    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": from_email},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body_text}],
        },
        timeout=10,
    )
    resp.raise_for_status()
