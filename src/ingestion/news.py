"""
Pulls NFL news from RSS feeds and stores normalized items.

Add beat-writer / team-specific feeds to FEEDS as you identify good sources.
Keep NewsAPI as a secondary/backup source for broader keyword coverage.
"""
import os
from datetime import datetime, timezone

import feedparser
import requests

from src.tracking.db import get_engine, init_db, upsert_rows

FEEDS = {
    "espn_nfl": "https://www.espn.com/espn/rss/nfl/news",
    # nfl.com/feeds/rss/news 404s as of 2026-08 -- NFL.com discontinued its
    # native RSS endpoint, no official replacement.
    "pft": "https://www.nbcsports.com/profootballtalk.rss",
    "cbs_sports_nfl": "https://www.cbssports.com/rss/headlines/nfl/",
    "yahoo_sports_nfl": "https://sports.yahoo.com/nfl/rss/",
    # Add more team/beat feeds here as you find them.
}


def fetch_rss_items() -> list[dict]:
    items = []
    for source, url in FEEDS.items():
        parsed = feedparser.parse(url)
        for entry in parsed.entries:
            items.append({
                "source": source,
                "url": entry.get("link"),
                "title": entry.get("title"),
                "published_at": entry.get("published"),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
    return items


def fetch_newsapi_items(query: str = "NFL") -> list[dict]:
    """Secondary source, keyword-filterable. Requires NEWS_API_KEY."""
    api_key = os.environ.get("NEWS_API_KEY")
    if not api_key:
        return []
    resp = requests.get(
        "https://newsapi.org/v2/everything",
        params={"q": query, "language": "en", "sortBy": "publishedAt", "apiKey": api_key},
        timeout=10,
    )
    resp.raise_for_status()
    articles = resp.json().get("articles", [])
    return [
        {
            "source": a.get("source", {}).get("name", "newsapi"),
            "url": a.get("url"),
            "title": a.get("title"),
            "published_at": a.get("publishedAt"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        for a in articles
    ]


def persist_news_items(engine, items: list[dict]) -> int:
    """Upsert news items, deduped by URL.

    Items without a URL can't be deduped, so they're dropped rather than
    accumulating as duplicates on every run.
    """
    rows = [item for item in items if item.get("url")]
    return upsert_rows(engine, "news_items", rows, unique_cols=["url"])


if __name__ == "__main__":
    engine = get_engine()
    init_db(engine)

    items = fetch_rss_items() + fetch_newsapi_items()
    n = persist_news_items(engine, items)
    print(f"Upserted {n} news items ({len(items)} fetched)")
