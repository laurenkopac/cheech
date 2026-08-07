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

# Same palette as src/newsletter/render.py's CATEGORY_COLORS/MARKET_BADGES
# (converted from those exact hex values), so the Discord and email
# channels read as one visual system rather than two unrelated designs.
# News alerts here are always injury/roster-signal by construction (see
# _INJURY_PATTERN), so they get the newsletter's "Injury" color.
NEWS_ALERT_COLOR = 0xB91C1C
MARKET_COLORS = {
    "winner": 0x0E7490,
    "anytime_td": 0x15803D,
    "first_td": 0x15803D,
}
DEFAULT_MARKET_COLOR = 0x52525B
MARKET_LABELS = {
    "winner": "Winner picks",
    "anytime_td": "Anytime TD",
    "first_td": "First TD scorer",
}


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


def format_news_alert(items: list[dict]) -> dict:
    """One field per item -- title as the field name, a markdown link to
    the source as the value -- in a single embed rather than a message
    per item, so a handful of same-run alerts read as one digest card."""
    return {
        "title": "🏈 Injury/roster news",
        "color": NEWS_ALERT_COLOR,
        "fields": [
            {"name": item["title"], "value": f"[{item['source']}](<{item['url']}>)", "inline": False}
            for item in items
        ],
    }


def format_predictions_alert(edges: list[dict]) -> dict:
    """One field per edge, all edges assumed to be the same market (as
    get_latest_model_edges returns) -- title/color are market-specific so
    winner and TD alerts read as visually distinct cards, matching the
    newsletter's Picks/TD pill colors (see MARKET_COLORS)."""
    market = edges[0]["market"] if edges else "winner"
    fields = []
    for edge in edges:
        value = f"{edge['predicted_probability']:.1%}"
        if edge["edge"] is not None:
            value += f" (edge {edge['edge']:.1%})"
        fields.append({"name": edge["subject"], "value": value, "inline": True})
    return {
        "title": f"📈 New model edges — {MARKET_LABELS.get(market, market.title())}",
        "color": MARKET_COLORS.get(market, DEFAULT_MARKET_COLOR),
        "fields": fields,
    }
