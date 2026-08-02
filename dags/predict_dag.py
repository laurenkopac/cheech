"""
Generates predictions ahead of each week's slate. Runs after stats/odds/news
ingestion so features reflect the latest information.
"""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator


def run_feature_build():
    print("Building features from latest ingested data")
    # TODO: call src.models.features functions


def run_predictions():
    print("Generating winner and TD predictions")
    # TODO: load trained models, predict, persist to predictions table


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
