"""
Hourly-in-season news ingestion from RSS + NewsAPI.
"""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.ingestion.news import fetch_rss_items, fetch_newsapi_items


def run_news_ingestion():
    items = fetch_rss_items() + fetch_newsapi_items()
    print(f"Fetched {len(items)} news items")
    # TODO: persist to news_items table, dedupe by URL


with DAG(
    dag_id="ingest_news",
    description="News ingestion from RSS and NewsAPI",
    schedule="0 * * * *",  # hourly
    start_date=datetime(2026, 8, 1),
    catchup=False,
    tags=["cheech", "ingestion"],
) as dag:
    PythonOperator(task_id="fetch_news", python_callable=run_news_ingestion)
