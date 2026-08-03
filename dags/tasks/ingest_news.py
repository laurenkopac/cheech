"""
Task logic for ingest_news_dag.py. Imports only from src.* (never airflow)
so it can run inside the `cheech` conda env via dags/_env.py -- see that
file's docstring for why the split exists.
"""
import os

from src.discord.content import filter_high_signal_news, format_news_alert, select_new_items
from src.discord.send import send_discord_message
from src.ingestion.news import fetch_rss_items, fetch_newsapi_items, persist_news_items
from src.tracking.db import get_engine, init_db


def run_news_ingestion():
    engine = get_engine()
    init_db(engine)
    items = fetch_rss_items() + fetch_newsapi_items()
    new_items = select_new_items(engine, items)
    n = persist_news_items(engine, items)
    print(f"Upserted {n} news items ({len(items)} fetched)")

    high_signal = filter_high_signal_news(new_items)
    webhook_url = os.environ.get("DISCORD_NEWS_WEBHOOK_URL")
    if high_signal and webhook_url:
        send_discord_message(format_news_alert(high_signal), webhook_url)
        print(f"Posted {len(high_signal)} high-signal item(s) to Discord")
    elif high_signal:
        print(f"{len(high_signal)} high-signal item(s) found but DISCORD_NEWS_WEBHOOK_URL isn't set -- skipping")


if __name__ == "__main__":
    import sys
    globals()[sys.argv[1]]()
