"""
Daily ingestion of nflverse stats: schedules, injuries, snap counts.
Play-by-play is heavier — run it less frequently (e.g. weekly, or after
each week's games complete) by adjusting the schedule below.
"""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.ingestion.stats import get_schedules, get_injuries, get_snap_counts

CURRENT_SEASON = 2026


def run_schedules():
    df = get_schedules([CURRENT_SEASON])
    print(f"Fetched {len(df)} schedule rows")
    # TODO: persist to DB


def run_injuries():
    df = get_injuries([CURRENT_SEASON])
    print(f"Fetched {len(df)} injury rows")
    # TODO: persist to DB


def run_snap_counts():
    df = get_snap_counts([CURRENT_SEASON])
    print(f"Fetched {len(df)} snap count rows")
    # TODO: persist to DB


with DAG(
    dag_id="ingest_stats",
    description="Daily nflverse stats ingestion",
    schedule="0 8 * * *",  # 8am daily
    start_date=datetime(2026, 8, 1),
    catchup=False,
    tags=["cheech", "ingestion"],
) as dag:
    schedules_task = PythonOperator(task_id="fetch_schedules", python_callable=run_schedules)
    injuries_task = PythonOperator(task_id="fetch_injuries", python_callable=run_injuries)
    snaps_task = PythonOperator(task_id="fetch_snap_counts", python_callable=run_snap_counts)

    schedules_task >> [injuries_task, snaps_task]
