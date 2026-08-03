"""
Sends the drafted newsletter via Gmail SMTP.

draft_newsletter() (see summarize.py) returns markdown -- plain MIMEText
showed that syntax raw (literal **, ##, etc.) in the email client, so this
renders it to styled HTML and sends multipart/alternative, with the raw
markdown kept as the plain-text fallback part.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown
from jinja2 import Template

HTML_TEMPLATE = Template("""\
<html>
  <head>
    <style>
      body { margin: 0; padding: 0; background-color: #f4f4f4; }
      .container {
        max-width: 600px; margin: 0 auto; padding: 24px;
        background-color: #ffffff;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        color: #1a1a1a; line-height: 1.5;
      }
      h1 { font-size: 22px; }
      h2 { font-size: 18px; margin-top: 28px; border-bottom: 2px solid #eee; padding-bottom: 6px; }
      a { color: #1a5fb4; }
      hr { border: none; border-top: 1px solid #eee; margin: 20px 0; }
      li { margin-bottom: 6px; }
    </style>
  </head>
  <body>
    <div class="container">{{ body|safe }}</div>
  </body>
</html>
""")


def send_newsletter(subject: str, body_text: str):
    from_email = os.environ.get("NEWSLETTER_FROM_EMAIL")
    to_email = os.environ.get("NEWSLETTER_TO_EMAIL")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not all([from_email, to_email, app_password]):
        raise RuntimeError("Missing Gmail SMTP config in environment variables")

    body_html = markdown.markdown(body_text, extensions=["extra", "sane_lists"])
    html = HTML_TEMPLATE.render(body=body_html)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    # Plain-text part first, HTML second -- clients that support both use
    # the last (HTML) part, so this order is what makes the fallback a
    # fallback rather than the default.
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(from_email, app_password)
        server.send_message(msg)
