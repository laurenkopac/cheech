"""
Hourly-in-season news ingestion from RSS + NewsAPI.
"""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.ingestion.news import fetch_rss_items, fetch_newsapi_items, persist_news_items
from src.tracking.db import get_engine, init_db


def run_news_ingestion():
    engine = get_engine()
    init_db(engine)
    items = fetch_rss_items() + fetch_newsapi_items()
    n = persist_news_items(engine, items)
    print(f"Upserted {n} news items ({len(items)} fetched)")


with DAG(
    dag_id="ingest_news",
    description="News ingestion from RSS and NewsAPI",
    schedule="0 * * * *",  # hourly
    start_date=datetime(2026, 8, 1),
    catchup=False,
    tags=["cheech", "ingestion"],
) as dag:
    PythonOperator(task_id="fetch_news", python_callable=run_news_ingestion)
