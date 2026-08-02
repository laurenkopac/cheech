"""
Feature engineering: turns raw ingested data (pbp, rosters, injuries,
odds, weather) into model-ready feature vectors.

Keep feature-building functions pure (input dataframes -> output dataframe)
so they're easy to unit test and re-run for backtesting.
"""
import pandas as pd


def build_team_game_features(pbp: pd.DataFrame, schedules: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate play-by-play into team-level, per-game features:
    EPA/play, success rate, pass/run split, red zone efficiency, etc.

    TODO: implement aggregation once pbp data is flowing.
    """
    raise NotImplementedError


def build_player_td_features(pbp: pd.DataFrame, rosters: pd.DataFrame) -> pd.DataFrame:
    """
    Per-player features for anytime-TD modeling: red-zone touches,
    target share, historical TD conversion rate, opponent defensive
    splits against the player's position.

    TODO: implement once pbp/rosters ingestion is in place.
    """
    raise NotImplementedError


def attach_odds_features(features: pd.DataFrame, odds: list[dict]) -> pd.DataFrame:
    """
    Merge in market-implied probabilities and line movement as features
    (the market is itself informative, and deviations from it are where
    edge tends to live).

    TODO: implement once odds ingestion is in place.
    """
    raise NotImplementedError
