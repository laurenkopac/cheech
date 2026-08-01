"""
Pulls NFL news from RSS feeds and stores normalized items.

Add beat-writer / team-specific feeds to FEEDS as you identify good sources.
Keep NewsAPI as a secondary/backup source for broader keyword coverage.
"""
import os
from datetime import datetime, timezone

import feedparser
import requests

FEEDS = {
    "espn_nfl": "https://www.espn.com/espn/rss/nfl/news",
    "nfl_news": "https://www.nfl.com/feeds/rss/news",
    # Add beat-writer / team feeds here as you find them.
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


if __name__ == "__main__":
    for item in fetch_rss_items()[:5]:
        print(item["source"], "-", item["title"])
