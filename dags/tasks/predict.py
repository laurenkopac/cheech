"""
Task logic for predict_dag.py. Imports only from src.* (never airflow) so
it can run inside the `cheech` conda env via dags/_env.py -- see that
file's docstring for why the split exists.
"""
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


if __name__ == "__main__":
    import sys
    globals()[sys.argv[1]]()
