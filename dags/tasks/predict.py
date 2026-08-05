"""
Task logic for predict_dag.py. Imports only from src.* (never airflow) so
it can run inside the `cheech` conda env via dags/_env.py -- see that
file's docstring for why the split exists.
"""
import os

from src.discord.content import format_predictions_alert
from src.discord.send import send_discord_message
from src.models.train import (
    build_features,
    build_player_features,
    persist_predictions,
    train_and_predict_anytime_td,
    train_and_predict_winner,
)
from src.newsletter.content import get_latest_model_edges
from src.tracking.db import get_engine, init_db

CURRENT_SEASON = 2026


def run_feature_build():
    team_features = build_features(CURRENT_SEASON)
    completed = team_features["home_score"].notna().sum()
    upcoming = team_features["home_score"].isna().sum()
    print(f"Built team features for {len(team_features)} games ({completed} completed, {upcoming} upcoming)")

    player_features = build_player_features(CURRENT_SEASON, team_features)
    real = player_features["anytime_td"].notna().sum()
    projected = player_features["anytime_td"].isna().sum()
    print(f"Built player features for {len(player_features)} player-games ({real} real, {projected} projected)")


def run_predictions():
    # Rebuilds features rather than reading run_feature_build()'s output --
    # Airflow XCom isn't a good fit for passing a season's worth of
    # DataFrames between tasks, and refetching/rebuilding takes a few
    # seconds at this data volume. Keeping each task self-contained is
    # simpler than wiring a shared-storage handoff just to avoid that.
    engine = get_engine()
    init_db(engine)

    team_features = build_features(CURRENT_SEASON)
    winner_predictions = train_and_predict_winner(team_features)
    if winner_predictions.empty:
        print("No winner predictions generated (no completed games to train on yet, or no upcoming games)")
    else:
        n = persist_predictions(engine, winner_predictions, market="winner")
        print(f"Persisted {n} winner predictions")

    player_features = build_player_features(CURRENT_SEASON, team_features)
    td_predictions = train_and_predict_anytime_td(player_features)
    if td_predictions.empty:
        print("No anytime-TD predictions generated (no completed games to train on yet, or no projected rows)")
    else:
        n = persist_predictions(engine, td_predictions, market="anytime_td")
        print(f"Persisted {n} anytime-TD predictions")

    # Discord alerting covers the winner model only for now -- see
    # CLAUDE.md "Discord Delivery" on splitting out a TD channel once
    # there's a reason to see TD edges faster than the daily newsletter.
    edges = get_latest_model_edges(engine, market="winner")
    webhook_url = os.environ.get("DISCORD_PREDICTIONS_WEBHOOK_URL")
    if edges and webhook_url:
        send_discord_message(format_predictions_alert(edges), webhook_url)
        print(f"Posted {len(edges)} model edge(s) to Discord")
    elif edges:
        print(f"{len(edges)} model edge(s) found but DISCORD_PREDICTIONS_WEBHOOK_URL isn't set -- skipping")


if __name__ == "__main__":
    import sys
    globals()[sys.argv[1]]()
