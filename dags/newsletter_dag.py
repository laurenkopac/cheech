"""
Daily newsletter: pulls the day's news + top model edges, summarizes with
citations, and emails it to the user.
"""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.newsletter.summarize import draft_newsletter
from src.newsletter.send import send_newsletter


def run_newsletter():
    # TODO: replace with real queries against news_items / predictions tables
    news_items: list[dict] = []
    model_edges: list[dict] = []

    if not news_items and not model_edges:
        print("No content available yet — skipping send until ingestion is wired up.")
        return

    body = draft_newsletter(news_items, model_edges)
    send_newsletter(subject="Your Daily Cheech Digest", body_text=body)


with DAG(
    dag_id="daily_newsletter",
    description="Daily curated NFL newsletter with source citations",
    schedule="0 7 * * *",  # 7am daily
    start_date=datetime(2026, 8, 1),
    catchup=False,
    tags=["cheech", "newsletter"],
) as dag:
    PythonOperator(task_id="build_and_send_newsletter", python_callable=run_newsletter)
