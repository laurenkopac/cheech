"""
Task logic for newsletter_dag.py. Imports only from src.* (never airflow)
so it can run inside the `cheech` conda env via dags/_env.py -- see that
file's docstring for why the split exists.
"""
from src.newsletter.content import get_latest_model_edges, get_recent_news_items
from src.newsletter.summarize import draft_newsletter
from src.newsletter.send import send_newsletter
from src.tracking.db import get_engine

MARKETS = ["winner", "anytime_td", "first_td"]


def run_newsletter():
    engine = get_engine()
    news_items = get_recent_news_items(engine)
    model_edges = [edge for market in MARKETS for edge in get_latest_model_edges(engine, market=market)]

    if not news_items and not model_edges:
        print("No content available yet — skipping send until ingestion is wired up.")
        return

    data = draft_newsletter(news_items, model_edges)
    send_newsletter(subject="Your Daily Cheech Digest", data=data)


if __name__ == "__main__":
    import sys
    globals()[sys.argv[1]]()
