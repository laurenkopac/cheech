"""
Daily ingestion of nflverse stats: schedules, injuries, snap counts.
Play-by-play is heavier — run it less frequently (e.g. weekly, or after
each week's games complete) by adjusting the schedule below.

Task logic lives in dags/tasks/ingest_stats.py and runs inside the `cheech`
conda env (see dags/_env.py) -- this file only holds Airflow's own DAG
definition, since Airflow runs in its own isolated env.
"""
import sys
from datetime import datetime
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

# Airflow's DAG bundle loader doesn't put the repo root on sys.path, so
# `dags._env` isn't importable as a package -- import _env directly
# relative to this file instead.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import run_in_cheech_env


def run_schedules():
    run_in_cheech_env("ingest_stats", "run_schedules")


def run_injuries():
    run_in_cheech_env("ingest_stats", "run_injuries")


def run_snap_counts():
    run_in_cheech_env("ingest_stats", "run_snap_counts")


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
