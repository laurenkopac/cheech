"""
Generates predictions ahead of each week's slate. Runs after stats/odds/news
ingestion so features reflect the latest information.

Only the winner model is wired up here. Anytime-TD prediction needs a
player-level projection step (current roster + each player's latest
trailing stats + the upcoming opponent) that build_player_td_features
doesn't provide -- it's driven entirely by play-by-play, so it only has
rows for games that have already been played. See src/models/train.py's
module docstring for the full explanation; that's a real design task of
its own, not a small addition here.

Task logic lives in dags/tasks/predict.py and runs inside the `cheech`
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


def run_feature_build():
    run_in_cheech_env("predict", "run_feature_build")


def run_predictions():
    run_in_cheech_env("predict", "run_predictions")


with DAG(
    dag_id="generate_predictions",
    description="Weekly prediction generation ahead of the slate",
    schedule="0 10 * * 2",  # Tuesday 10am, after MNF completes
    start_date=datetime(2026, 8, 1),
    catchup=False,
    tags=["cheech", "modeling"],
) as dag:
    features_task = PythonOperator(task_id="build_features", python_callable=run_feature_build)
    predict_task = PythonOperator(task_id="generate_predictions", python_callable=run_predictions)

    features_task >> predict_task
