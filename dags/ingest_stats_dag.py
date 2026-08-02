"""
Daily ingestion of nflverse stats: schedules, injuries, snap counts.
Play-by-play is heavier — run it less frequently (e.g. weekly, or after
each week's games complete) by adjusting the schedule below.
"""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.ingestion.stats import persist_schedules, persist_injuries, persist_snap_counts
from src.tracking.db import get_engine, init_db

CURRENT_SEASON = 2026


def run_schedules():
    engine = get_engine()
    init_db(engine)
    n = persist_schedules(engine, [CURRENT_SEASON])
    print(f"Upserted {n} schedule rows")


def run_injuries():
    engine = get_engine()
    n = persist_injuries(engine, [CURRENT_SEASON])
    print(f"Upserted {n} injury rows")


def run_snap_counts():
    engine = get_engine()
    n = persist_snap_counts(engine, [CURRENT_SEASON])
    print(f"Upserted {n} snap count rows")


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
