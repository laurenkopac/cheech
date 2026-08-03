"""
Formats news items and model edges into Discord messages, and picks out
which items are worth an interrupt. CLAUDE.md's daily email already covers
the full day's news and top edges -- this channel is for signal that
shouldn't wait for the next morning's digest, so it filters down rather
than mirroring the newsletter's content 1:1.
"""
import re

from sqlalchemy import bindparam, text

# Word-boundary match, not substring -- a plain "out" would false-positive
# on "without", "shoutout", etc.
_INJURY_KEYWORDS = (
    "injury", "injured", "questionable", "doubtful", "ruled out",
    "day-to-day", "ir", "dnp", "limited participation", "waived",
    "activated", "placed on ir",
)
_INJURY_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _INJURY_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def select_new_items(engine, items: list[dict]) -> list[dict]:
    """Items not already present in news_items.

    upsert_rows refreshes fetched_at on every run, even for items already
    seen in a prior run (still-live RSS entries get re-upserted as-is) --
    so "fetched in the last hour" isn't the same as "new since last run".
    Checking against URLs already in the table before this run's upsert
    is what actually answers "is this new".
    """
    urls = [item["url"] for item in items if item.get("url")]
    if not urls:
        return []

    stmt = text("SELECT url FROM news_items WHERE url IN :urls").bindparams(
        bindparam("urls", expanding=True)
    )
    with engine.begin() as conn:
        existing = {row[0] for row in conn.execute(stmt, {"urls": urls})}

    return [item for item in items if item.get("url") and item["url"] not in existing]


def filter_high_signal_news(items: list[dict]) -> list[dict]:
    return [item for item in items if _INJURY_PATTERN.search(item.get("title") or "")]


def format_news_alert(items: list[dict]) -> str:
    lines = ["**🏈 Injury/roster news**"]
    for item in items:
        lines.append(f"- [{item['title']}](<{item['url']}>) — {item['source']}")
    return "\n".join(lines)


def format_predictions_alert(edges: list[dict]) -> str:
    lines = ["**📈 New model edges**"]
    for edge in edges:
        line = f"- {edge['subject']}: {edge['predicted_probability']:.1%}"
        if edge["edge"] is not None:
            line += f" (edge {edge['edge']:.1%})"
        lines.append(line)
    return "\n".join(lines)
