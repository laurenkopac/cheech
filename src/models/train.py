"""
Trains the winner and anytime-TD models on completed games and generates
predictions for upcoming ones, persisting each prediction with the exact
feature snapshot used to produce it (see sql/schema.sql: `predictions` is
append-only, one row per generation run, matching CLAUDE.md's ask to keep
pre-news and post-news predictions independently comparable).
"""
import json
from datetime import datetime, timezone
from urllib.error import HTTPError

import pandas as pd

from src.ingestion.odds import get_closing_odds_for_games, get_current_odds
from src.ingestion.stats import get_injuries, get_play_by_play, get_rosters, get_schedules
from src.models.features import attach_odds_features, build_player_td_features, build_team_game_features
from src.models.td_model import predict_anytime_td_probabilities, train_anytime_td_model
from src.models.winner_model import predict_winner_probabilities, train_winner_model
from src.tracking.db import get_engine, init_db, upsert_rows

CATEGORICAL_COLS = ["roof", "surface"]
NON_FEATURE_COLS = {
    "game_id", "season", "week", "game_type", "gameday", "home_team", "away_team",
    "home_score", "away_score",
}

PLAYER_FEATURE_COLS = [
    "touches_trailing", "redzone_touches_trailing", "target_share_trailing",
    "anytime_td_trailing", "opponent_position_td_rate_allowed_trailing",
    "team_redzone_td_rate_trailing", "team_implied_total", "teammates_out_count",
]
PLAYER_CATEGORICAL_COLS = ["position"]

INJURY_COLS = ["season", "week", "team", "gsis_id", "full_name", "position", "report_status", "practice_status"]


def _next_upcoming_week_mask(features: pd.DataFrame, is_completed: pd.Series) -> pd.Series:
    """
    True only for rows that are both upcoming and in the single nearest
    upcoming week.

    predict_dag runs weekly (Tuesday, ahead of that week's slate) -- both
    train_and_predict_winner and train_and_predict_anytime_td used to
    predict on *every* remaining week of the season each run, since
    build_team_game_features/build_player_td_features both build a row for
    every game/projected player-game regardless of week. That's more than
    the DAG needs (only the upcoming week's slate is actionable right now)
    and makes each week's prediction snapshot a poor match for CLV
    tracking, which assumes a prediction was made close to when the odds
    it's compared against actually reflect that week's line, not weeks
    early. Restricting to the single nearest upcoming week keeps each
    week's `generated_at` snapshot meaning "this week's predictions," and
    naturally refreshes as bye weeks/injuries/lineup changes happen closer
    to kickoff, rather than locking in a prediction made a month out.
    """
    upcoming_weeks = features.loc[~is_completed, "week"]
    if upcoming_weeks.empty:
        return pd.Series(False, index=features.index)
    next_week = upcoming_weeks.min()
    return (~is_completed) & (features["week"] == next_week)


def build_features(season: int, engine=None) -> pd.DataFrame:
    """Fetch pbp/schedules/odds live and build one season's team-game
    features, covering both completed and upcoming games.

    Live odds (get_current_odds()) only ever cover currently-listed,
    not-yet-played games -- attaching them alone leaves market_* columns
    NaN for every completed game, which is most of a season's training
    data. If `engine` is given, also reconstructs each played game's
    closing line from persisted odds_snapshots history
    (get_closing_odds_for_games) and fills in whatever live odds didn't
    match. Only as good as how much snapshot history has actually
    accumulated (requires ingest_odds_dag to have been running, or manual
    invocation, before those games kicked off) -- games with no snapshot
    on record just stay NaN, same as the existing "unmatched odds" case.
    """
    pbp = get_play_by_play([season])
    schedules = get_schedules([season])
    team_features = build_team_game_features(pbp, schedules)

    team_features = attach_odds_features(team_features, get_current_odds())

    if engine is not None:
        historical_odds = get_closing_odds_for_games(engine, schedules)
        if historical_odds:
            historical_attached = attach_odds_features(team_features, historical_odds)
            odds_cols = ["market_implied_home_win_prob", "market_spread_line", "market_total_line", "n_bookmakers"]
            for col in odds_cols:
                team_features[col] = team_features[col].fillna(historical_attached[col])

    return team_features


def train_and_predict_winner(team_features: pd.DataFrame) -> pd.DataFrame:
    """
    Trains XGBoost on completed games (home_score not null) and predicts
    on the single nearest upcoming week's games (see
    _next_upcoming_week_mask). Returns one row per game in that week:
    game_id, subject (home team), predicted_probability, feature_snapshot
    (JSON of that game's exact feature row) -- ready for
    persist_predictions(). Empty if there's no training data yet (e.g.
    early preseason, before any games this season have been played) or
    no upcoming games left to predict.

    Categoricals (roof/surface) are one-hot encoded across the *combined*
    train+predict rows before splitting, so both sets end up with
    identical columns -- encoding them separately could produce a
    category in one set that's absent from the other, which XGBoost's
    predict() would reject.
    """
    feature_cols = [c for c in team_features.columns if c not in NON_FEATURE_COLS]
    matrix = pd.get_dummies(
        team_features[feature_cols],
        columns=[c for c in CATEGORICAL_COLS if c in feature_cols],
    )

    is_completed = team_features["home_score"].notna()
    labels = (team_features["home_score"] > team_features["away_score"]).astype(int)

    X_train, y_train = matrix[is_completed], labels[is_completed]
    is_next_week = _next_upcoming_week_mask(team_features, is_completed)
    X_predict = matrix[is_next_week]
    if X_train.empty or X_predict.empty:
        return pd.DataFrame(columns=["game_id", "subject", "predicted_probability", "feature_snapshot"])

    model = train_winner_model(X_train, y_train)
    probs = predict_winner_probabilities(model, X_predict)

    # Round-trip through to_json to normalize NaN/numpy types into plain
    # JSON (same trick used in src/ingestion/stats.py).
    snapshots = json.loads(X_predict.to_json(orient="records"))

    upcoming = team_features.loc[is_next_week, ["game_id", "home_team"]].rename(columns={"home_team": "subject"})
    upcoming = upcoming.assign(
        predicted_probability=probs.values,
        feature_snapshot=[json.dumps(s) for s in snapshots],
    )
    return upcoming[["game_id", "subject", "predicted_probability", "feature_snapshot"]]


def build_player_features(season: int, team_features: pd.DataFrame) -> pd.DataFrame:
    """Fetch pbp/rosters/schedules/injuries live and build one season's
    player-game TD features, covering both completed and (via the current
    roster's upcoming schedule) projected upcoming games.

    `team_features` should be build_features(season)'s output (team-game
    features with odds already attached) -- passed in rather than
    refetched here, both because it's needed for team-level TD context
    (own-team red-zone efficiency, vegas-implied team total) and because
    calling get_current_odds() a second time per predict_dag run would
    burn through the Odds API's free-tier rate limit for no reason.
    """
    pbp = get_play_by_play([season])
    rosters = get_rosters([season])
    schedules = get_schedules([season])
    try:
        injuries = get_injuries([season])
    except HTTPError:
        # Same story as build_team_game_features's empty-pbp tolerance --
        # nflverse hasn't published an injury report for this season yet
        # (true every year until Week 1).
        injuries = pd.DataFrame(columns=INJURY_COLS)
    return build_player_td_features(pbp, rosters, schedules, team_features=team_features, injuries=injuries)


def train_and_predict_anytime_td(player_features: pd.DataFrame) -> pd.DataFrame:
    """
    Trains XGBoost on real player-games (anytime_td not null) and predicts
    on projected player-games in the single nearest upcoming week (see
    _next_upcoming_week_mask; projected rows themselves come from
    build_player_td_features). Returns one row per projected player-game
    in that week: game_id, subject ("Player Name (TEAM)"),
    predicted_probability, feature_snapshot. Empty if there's no training
    data yet or no projected rows to predict on (e.g. before Week 1, when
    no games have been played this season and no player has real trailing
    history to project from).
    """
    matrix = pd.get_dummies(
        player_features[PLAYER_FEATURE_COLS + PLAYER_CATEGORICAL_COLS],
        columns=PLAYER_CATEGORICAL_COLS,
    )

    is_completed = player_features["anytime_td"].notna()
    labels = player_features["anytime_td"].fillna(0).astype(int)

    X_train, y_train = matrix[is_completed], labels[is_completed]
    is_next_week = _next_upcoming_week_mask(player_features, is_completed)
    X_predict = matrix[is_next_week]
    if X_train.empty or X_predict.empty:
        return pd.DataFrame(columns=["game_id", "subject", "predicted_probability", "feature_snapshot"])

    model = train_anytime_td_model(X_train, y_train)
    probs = predict_anytime_td_probabilities(model, X_predict)

    snapshots = json.loads(X_predict.to_json(orient="records"))

    upcoming = player_features.loc[is_next_week, ["game_id", "player_name", "team"]]
    subjects = upcoming["player_name"].fillna("Unknown player") + " (" + upcoming["team"].fillna("?") + ")"
    upcoming = upcoming.assign(
        subject=subjects.values,
        predicted_probability=probs.values,
        feature_snapshot=[json.dumps(s) for s in snapshots],
    )
    return upcoming[["game_id", "subject", "predicted_probability", "feature_snapshot"]]


def persist_predictions(engine, predictions: pd.DataFrame, market: str) -> int:
    """Append predictions as a new timestamped snapshot -- like
    odds_snapshots, never upserted over a prior run's predictions."""
    if predictions.empty:
        return 0
    generated_at = datetime.now(timezone.utc).isoformat()
    rows = predictions.assign(market=market, generated_at=generated_at).to_dict(orient="records")
    return upsert_rows(engine, "predictions", rows, unique_cols=["generated_at", "market", "game_id", "subject"])


if __name__ == "__main__":
    season = 2026
    engine = get_engine()
    init_db(engine)

    print(f"Building features for {season}...")
    team_features = build_features(season, engine)
    print(f"team_features: {team_features.shape}, "
          f"completed={team_features['home_score'].notna().sum()}, "
          f"upcoming={team_features['home_score'].isna().sum()}, "
          f"with_market_data={team_features['market_spread_line'].notna().sum()}")

    predictions = train_and_predict_winner(team_features)
    print(f"Generated {len(predictions)} winner predictions")

    if not predictions.empty:
        n = persist_predictions(engine, predictions, market="winner")
        print(f"Upserted {n} prediction rows")
        print(predictions[["game_id", "subject", "predicted_probability"]].head(10))
    else:
        print("No winner predictions to persist (no completed games to train on yet, or no upcoming games).")

    print(f"\nBuilding player features for {season}...")
    player_features = build_player_features(season, team_features)
    print(f"player_features: {player_features.shape}, "
          f"real={player_features['anytime_td'].notna().sum()}, "
          f"projected={player_features['anytime_td'].isna().sum()}")

    td_predictions = train_and_predict_anytime_td(player_features)
    print(f"Generated {len(td_predictions)} anytime-TD predictions")

    if not td_predictions.empty:
        n = persist_predictions(engine, td_predictions, market="anytime_td")
        print(f"Upserted {n} anytime-TD prediction rows")
        print(td_predictions.sort_values("predicted_probability", ascending=False)
              [["game_id", "subject", "predicted_probability"]].head(10))
    else:
        print("No anytime-TD predictions to persist (no completed games to train on yet, or no projected rows).")
