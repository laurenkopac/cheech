"""
Task logic for ingest_news_dag.py. Imports only from src.* (never airflow)
so it can run inside the `cheech` conda env via dags/_env.py -- see that
file's docstring for why the split exists.
"""
from src.ingestion.news import fetch_rss_items, fetch_newsapi_items, persist_news_items
from src.tracking.db import get_engine, init_db


def run_news_ingestion():
    engine = get_engine()
    init_db(engine)
    items = fetch_rss_items() + fetch_newsapi_items()
    n = persist_news_items(engine, items)
    print(f"Upserted {n} news items ({len(items)} fetched)")


if __name__ == "__main__":
    import sys
    globals()[sys.argv[1]]()
