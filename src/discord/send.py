"""
Posts messages to a Discord channel via an incoming webhook.

Different content types go to different channels (news vs. predictions),
so the webhook URL is the caller's responsibility -- see dags/tasks/ for
which env var backs which channel.
"""
import requests

DISCORD_CONTENT_LIMIT = 2000


def send_discord_message(content: str, webhook_url: str):
    if not webhook_url:
        raise RuntimeError("Missing Discord webhook URL")

    if len(content) > DISCORD_CONTENT_LIMIT:
        content = content[: DISCORD_CONTENT_LIMIT - 1] + "…"

    response = requests.post(webhook_url, json={"content": content}, timeout=10)
    response.raise_for_status()
