"""
Frequent odds ingestion — run often enough to capture meaningful line
movement without burning through API quota. Every few hours is a
reasonable starting cadence.
"""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.ingestion.odds import get_current_odds


def run_odds_ingestion():
    games = get_current_odds()
    print(f"Fetched odds for {len(games)} games")
    # TODO: persist snapshot with timestamp for line-movement tracking


with DAG(
    dag_id="ingest_odds",
    description="Odds/line ingestion for line-movement tracking",
    schedule="0 */4 * * *",  # every 4 hours
    start_date=datetime(2026, 8, 1),
    catchup=False,
    tags=["cheech", "ingestion"],
) as dag:
    PythonOperator(task_id="fetch_odds", python_callable=run_odds_ingestion)
