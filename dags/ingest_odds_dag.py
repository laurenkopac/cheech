"""
Frequent odds ingestion — run often enough to capture meaningful line
movement without burning through API quota. Every few hours is a
reasonable starting cadence.
"""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.ingestion.odds import get_current_odds, persist_odds_snapshot
from src.tracking.db import get_engine, init_db


def run_odds_ingestion():
    engine = get_engine()
    init_db(engine)
    games = get_current_odds()
    n = persist_odds_snapshot(engine, games)
    print(f"Upserted {n} odds snapshot rows for {len(games)} games")


with DAG(
    dag_id="ingest_odds",
    description="Odds/line ingestion for line-movement tracking",
    schedule="0 */4 * * *",  # every 4 hours
    start_date=datetime(2026, 8, 1),
    catchup=False,
    tags=["cheech", "ingestion"],
) as dag:
    PythonOperator(task_id="fetch_odds", python_callable=run_odds_ingestion)
