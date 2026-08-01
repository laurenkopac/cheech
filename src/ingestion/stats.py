"""
Pulls core NFL stats via nfl_data_py (nflverse): play-by-play, rosters,
injuries, snap counts, schedules.

This is the backbone data source — most feature engineering starts here.
"""
import nfl_data_py as nfl


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


if __name__ == "__main__":
    current_year = 2026
    df = get_schedules([current_year])
    print(df.head())
    print(f"{len(df)} games loaded for {current_year}")
