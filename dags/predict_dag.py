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
"""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.models.train import build_features, persist_predictions, train_and_predict_winner
from src.tracking.db import get_engine, init_db

CURRENT_SEASON = 2026


def run_feature_build():
    team_features = build_features(CURRENT_SEASON)
    completed = team_features["home_score"].notna().sum()
    upcoming = team_features["home_score"].isna().sum()
    print(f"Built features for {len(team_features)} games ({completed} completed, {upcoming} upcoming)")


def run_predictions():
    # Rebuilds features rather than reading run_feature_build()'s output --
    # Airflow XCom isn't a good fit for passing a season's worth of
    # DataFrames between tasks, and refetching/rebuilding takes a few
    # seconds at this data volume. Keeping each task self-contained is
    # simpler than wiring a shared-storage handoff just to avoid that.
    team_features = build_features(CURRENT_SEASON)
    predictions = train_and_predict_winner(team_features)
    if predictions.empty:
        print("No predictions generated (no completed games to train on yet, or no upcoming games)")
        return

    engine = get_engine()
    init_db(engine)
    n = persist_predictions(engine, predictions, market="winner")
    print(f"Persisted {n} winner predictions")


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
