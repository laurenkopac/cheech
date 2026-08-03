"""
Daily newsletter: pulls the day's news + top model edges, summarizes with
citations, and emails it to the user.

Task logic lives in dags/tasks/newsletter.py and runs inside the `cheech`
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


def run_newsletter():
    run_in_cheech_env("newsletter", "run_newsletter")


with DAG(
    dag_id="daily_newsletter",
    description="Daily curated NFL newsletter with source citations",
    schedule="0 7 * * *",  # 7am daily
    start_date=datetime(2026, 8, 1),
    catchup=False,
    tags=["cheech", "newsletter"],
) as dag:
    PythonOperator(task_id="build_and_send_newsletter", python_callable=run_newsletter)
