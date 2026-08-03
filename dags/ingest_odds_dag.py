"""
Frequent odds ingestion — run often enough to capture meaningful line
movement without burning through API quota. Every few hours is a
reasonable starting cadence.

Task logic lives in dags/tasks/ingest_odds.py and runs inside the `cheech`
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


def run_odds_ingestion():
    run_in_cheech_env("ingest_odds", "run_odds_ingestion")


with DAG(
    dag_id="ingest_odds",
    description="Odds/line ingestion for line-movement tracking",
    schedule="0 */4 * * *",  # every 4 hours
    start_date=datetime(2026, 8, 1),
    catchup=False,
    tags=["cheech", "ingestion"],
) as dag:
    PythonOperator(task_id="fetch_odds", python_callable=run_odds_ingestion)
