"""
Pulls core NFL stats via nfl_data_py (nflverse): play-by-play, rosters,
injuries, snap counts, schedules.

This is the backbone data source — most feature engineering starts here.
"""
import json
from datetime import datetime, timezone
from urllib.error import HTTPError

import nfl_data_py as nfl

from src.tracking.db import get_engine, init_db, upsert_rows


def get_schedules(years: list[int]):
    """Season schedules, including scores once games are complete."""
    return nfl.import_schedules(years)


def get_play_by_play(years: list[int]):
    """Play-by-play data — EPA, WPA, down/distance, personnel, etc."""
    return nfl.import_pbp_data(years)


def get_rosters(years: list[int]):
    return nfl.import_seasonal_rosters(years)


def get_injuries(years: list[int]):
    return nfl.import_injuries(years)


def get_snap_counts(years: list[int]):
    return nfl.import_snap_counts(years)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rows_with_raw_json(df, structured_cols: list[str]) -> list[dict]:
    """Build upsert-ready rows: a few structured columns plus the full
    source row as JSON. Round-tripping through df.to_json() (rather than
    df.to_dict()) converts NaN -> None and numpy scalars -> native Python
    types, both of which the sqlite driver and json.dumps otherwise choke
    on.
    """
    fetched_at = _now()
    records = json.loads(df.to_json(orient="records"))
    rows = []
    for record in records:
        row = {col: record.get(col) for col in structured_cols}
        row["raw_json"] = json.dumps(record)
        row["fetched_at"] = fetched_at
        rows.append(row)
    return rows


def persist_schedules(engine, years: list[int]) -> int:
    df = get_schedules(years)
    rows = _rows_with_raw_json(df, [
        "game_id", "season", "week", "game_type", "gameday",
        "home_team", "away_team", "home_score", "away_score",
    ])
    return upsert_rows(engine, "schedules", rows, unique_cols=["game_id"])


def persist_injuries(engine, years: list[int]) -> int:
    try:
        df = get_injuries(years)
    except HTTPError:
        # nflverse hasn't published an injury report for this season yet
        # (true every year until Week 1) -- not a failure, just no data.
        print(f"No injury report available yet for {years}")
        return 0
    rows = _rows_with_raw_json(df, [
        "season", "week", "team", "gsis_id", "full_name",
        "position", "report_status", "practice_status",
    ])
    return upsert_rows(engine, "injuries", rows, unique_cols=["season", "week", "team", "gsis_id"])


def persist_snap_counts(engine, years: list[int]) -> int:
    try:
        df = get_snap_counts(years)
    except HTTPError:
        # Same story as injuries: no snaps to report before games are played.
        print(f"No snap count data available yet for {years}")
        return 0
    rows = _rows_with_raw_json(df, [
        "game_id", "pfr_player_id", "player", "team",
        "position", "offense_pct", "defense_pct", "st_pct",
    ])
    return upsert_rows(engine, "snap_counts", rows, unique_cols=["game_id", "pfr_player_id"])


if __name__ == "__main__":
    current_year = 2026
    engine = get_engine()
    init_db(engine)

    n = persist_schedules(engine, [current_year])
    print(f"Upserted {n} schedule rows for {current_year}")

    n = persist_injuries(engine, [current_year])
    print(f"Upserted {n} injury rows for {current_year}")

    n = persist_snap_counts(engine, [current_year])
    print(f"Upserted {n} snap count rows for {current_year}")
