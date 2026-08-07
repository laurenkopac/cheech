"""
Posts a rich embed to a Discord channel via an incoming webhook.

Different content types go to different channels (news vs. predictions),
so the webhook URL is the caller's responsibility -- see dags/tasks/ for
which env var backs which channel.
"""
import requests

# Discord's documented embed limits (per embed, not per message) --
# https://discord.com/developers/docs/resources/message#embed-object-embed-limits
TITLE_LIMIT = 256
FIELD_NAME_LIMIT = 256
FIELD_VALUE_LIMIT = 1024
FIELD_COUNT_LIMIT = 25


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def send_discord_embed(embed: dict, webhook_url: str):
    """`embed` is a plain dict shaped like Discord's embed object (title,
    color, fields: [{name, value, inline}], ...) -- see src/discord/content.py
    for what builds these. Truncates to Discord's documented per-field
    limits rather than letting an oversized embed 400 at send time; caps
    field count at 25 (Discord's hard limit) by dropping the rest, since
    the callers building these already narrow content down to a small,
    genuinely high-signal set (top-N edges, high-signal news only) and
    silently dropping the tail is a reasonable degrade, not data loss.
    """
    if not webhook_url:
        raise RuntimeError("Missing Discord webhook URL")

    embed = dict(embed)
    if "title" in embed:
        embed["title"] = _truncate(embed["title"], TITLE_LIMIT)
    if "fields" in embed:
        fields = embed["fields"][:FIELD_COUNT_LIMIT]
        embed["fields"] = [
            {**f, "name": _truncate(f["name"], FIELD_NAME_LIMIT), "value": _truncate(f["value"], FIELD_VALUE_LIMIT)}
            for f in fields
        ]

    response = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
    response.raise_for_status()
