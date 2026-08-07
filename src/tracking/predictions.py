"""
Read path over the append-only `predictions` table (sql/schema.sql) for the
Predictions dashboard page. Every prediction run is a new timestamped row,
never an upsert, so "the current slate" always means the latest
generated_at per market -- which also happens to mean "this week's games",
since predict_dag only ever predicts the single nearest upcoming week (see
_next_upcoming_week_mask in src/models/train.py). No separate week filter
is needed here as a result.
"""
import json

import pandas as pd
from sqlalchemy import text

MARKETS = ["winner", "anytime_td", "first_td"]


def get_latest_predictions(engine, market: str) -> pd.DataFrame:
    """The most recent generation run's predictions for `market`, joined
    with schedules for matchup context (teams, week, kickoff). Empty
    DataFrame (with the expected columns, so callers can rely on them
    existing) if no predictions have been persisted for this market yet.

    Includes `edge` -- |predicted_probability - market_implied_home_win_prob|,
    pulled out of feature_snapshot -- for markets that have one (currently
    just "winner"; TD markets have no odds join, so edge is always None
    for them, same convention as get_latest_model_edges in
    src/newsletter/content.py).
    """
    empty_cols = [
        "game_id", "subject", "predicted_probability", "generated_at",
        "season", "week", "gameday", "home_team", "away_team", "edge",
    ]

    with engine.begin() as conn:
        latest_run = conn.execute(
            text("SELECT MAX(generated_at) FROM predictions WHERE market = :market"),
            {"market": market},
        ).scalar()
        if latest_run is None:
            return pd.DataFrame(columns=empty_cols)

        rows = conn.execute(
            text("""
                SELECT p.game_id, p.subject, p.predicted_probability, p.generated_at,
                       p.feature_snapshot, s.season, s.week, s.gameday, s.home_team, s.away_team
                FROM predictions p
                LEFT JOIN schedules s ON s.game_id = p.game_id
                WHERE p.market = :market AND p.generated_at = :generated_at
            """),
            {"market": market, "generated_at": latest_run},
        ).mappings().all()

    if not rows:
        return pd.DataFrame(columns=empty_cols)

    df = pd.DataFrame([dict(row) for row in rows])

    if market == "winner":
        market_prob = df["feature_snapshot"].map(
            lambda s: json.loads(s).get("market_implied_home_win_prob")
        )
        df["edge"] = (df["predicted_probability"] - market_prob).abs()
    else:
        df["edge"] = None

    return df.drop(columns=["feature_snapshot"]).sort_values(
        ["gameday", "game_id"], na_position="last"
    ).reset_index(drop=True)


def get_current_week_label(predictions_by_market: dict[str, pd.DataFrame]) -> str | None:
    """A single "Week N" label for the slate, taken from whichever market
    has predictions -- all three are generated from the same
    _next_upcoming_week_mask in the same predict_dag run, so they agree on
    week whenever more than one market has data. None if every market is
    empty (nothing predicted yet)."""
    for df in predictions_by_market.values():
        if not df.empty and df["week"].notna().any():
            return f"Week {int(df['week'].dropna().iloc[0])}"
    return None
