"""
Feature engineering: turns raw ingested data (pbp, rosters, injuries,
odds, weather) into model-ready feature vectors.

Keep feature-building functions pure (input dataframes -> output dataframe)
so they're easy to unit test and re-run for backtesting.

pbp/rosters/schedules are passed in rather than read from the DB -- only
schedules/injuries/snap_counts/odds/news/bets are persisted (see
sql/schema.sql). Play-by-play in particular is heavy (~400 columns,
tens of thousands of rows/season) and isn't stored; callers fetch it live
via nfl_data_py (see src/ingestion/stats.py) right before building
features.
"""
import numpy as np
import pandas as pd

RED_ZONE_YARDLINE = 20

# Full-name -> abbreviation, for joining The Odds API's team names onto
# nflverse's abbreviations (schedules/pbp use "SEA", the odds API uses
# "Seattle Seahawks"). Sourced from nfl_data_py.import_team_desc(),
# filtered to the 32 abbreviations schedules actually uses today (drops
# legacy duplicates like OAK/SD/STL and the unused "LAR" alt-abbreviation
# for the Rams -- schedules uses "LA"). Static rather than fetched at call
# time so attach_odds_features stays a pure, offline function; 32 team
# names/abbreviations essentially never change mid-season.
TEAM_NAME_TO_ABBR = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    "Los Angeles Rams": "LA",
    "Los Angeles Chargers": "LAC",
    "Las Vegas Raiders": "LV",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "Seattle Seahawks": "SEA",
    "San Francisco 49ers": "SF",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
}


def _trailing_average(
    df: pd.DataFrame,
    group_cols: list[str],
    order_col: str,
    value_cols: list[str],
    suffix: str = "_trailing",
) -> pd.DataFrame:
    """
    Add `<col><suffix>` columns holding the expanding, group-to-date mean
    of each of `value_cols`, using only *prior* rows within each group
    (ordered by `order_col`) -- the current row's own value is excluded.

    This is what makes team/player performance stats safe to use as a
    pre-game feature: a team's EPA *in the game being predicted* is a
    near-direct proxy for whether it won, so a raw same-game aggregate
    would leak the outcome. The shifted, trailing version only reflects
    what was known before the game started. The first row in each group
    (e.g. a team's week-1 game) gets NaN -- left as-is rather than
    imputed, since XGBoost handles missing values natively.
    """
    df = df.sort_values(order_col)
    shifted = (
        df.groupby(group_cols, group_keys=False)[value_cols]
        .apply(lambda g: g.shift(1).expanding().mean())
    )
    out = df.copy()
    for col in value_cols:
        out[f"{col}{suffix}"] = shifted[col]
    return out


def _american_to_prob(odds: float) -> float:
    """American odds -> implied probability (includes the bookmaker's vig)."""
    if odds > 0:
        return 100 / (odds + 100)
    return -odds / (-odds + 100)


def build_team_game_features(pbp: pd.DataFrame, schedules: pd.DataFrame) -> pd.DataFrame:
    """
    One row per game_id with home_*/away_* trailing team-efficiency
    features (EPA/play, success rate, pass rate, red-zone TD rate,
    turnovers -- both offense and "allowed" defense), plus schedule
    context already sitting unused in `schedules` (rest days, division
    game, roof/surface/weather) and the game's identifying/outcome
    columns (season, week, teams, scores).

    All `*_trailing` columns are season-to-date averages entering this
    game (see _trailing_average) -- never this game's own stats, so
    they're safe to train a pre-game winner model on. Upcoming, unplayed
    games (no pbp rows yet) are included too, with trailing features
    forward-filled from each team's most recent played game -- that's
    what makes this usable for generating predictions, not just training.

    Tolerates `pbp` being completely empty (nfl_data_py returns an empty,
    columnless DataFrame -- rather than raising -- for a season with no
    games played yet, e.g. preseason before Week 1): in that case every
    team-game's stats are simply unknown/NaN, same as any other team's
    week-1 game.
    """
    STAT_SUFFIXES = ["epa_per_play", "success_rate", "pass_rate", "plays", "turnovers", "redzone_td_rate"]

    def _side_stats(plays: pd.DataFrame, group_col: str, prefix: str) -> pd.DataFrame:
        agg = (
            plays.groupby([group_col, "game_id"])
            .agg(**{
                f"{prefix}_epa_per_play": ("epa", "mean"),
                f"{prefix}_success_rate": ("success", "mean"),
                f"{prefix}_pass_rate": ("pass_attempt", "mean"),
                f"{prefix}_plays": ("epa", "size"),
                f"{prefix}_interceptions": ("interception", "sum"),
                f"{prefix}_fumbles_lost": ("fumble_lost", "sum"),
            })
            .reset_index()
            .rename(columns={group_col: "team"})
        )
        agg[f"{prefix}_turnovers"] = agg[f"{prefix}_interceptions"] + agg[f"{prefix}_fumbles_lost"]
        agg = agg.drop(columns=[f"{prefix}_interceptions", f"{prefix}_fumbles_lost"])

        rz_plays = plays[plays["yardline_100"] <= RED_ZONE_YARDLINE]
        rz_drives = (
            rz_plays.groupby([group_col, "game_id", "fixed_drive"])["fixed_drive_result"]
            .first()
            .reset_index()
            .rename(columns={group_col: "team"})
        )
        rz_summary = (
            rz_drives.groupby(["team", "game_id"])["fixed_drive_result"]
            .agg(**{
                f"{prefix}_redzone_trips": "size",
                f"{prefix}_redzone_tds": lambda s: (s == "Touchdown").sum(),
            })
            .reset_index()
        )
        rz_summary[f"{prefix}_redzone_td_rate"] = (
            rz_summary[f"{prefix}_redzone_tds"] / rz_summary[f"{prefix}_redzone_trips"]
        )
        return agg.merge(
            rz_summary[["team", "game_id", f"{prefix}_redzone_td_rate"]],
            on=["team", "game_id"],
            how="left",
        )

    if pbp.empty or "epa" not in pbp.columns:
        empty_cols = ["team", "game_id"] + [f"{p}_{s}" for p in ("off", "def") for s in STAT_SUFFIXES]
        played_stats = pd.DataFrame(columns=empty_cols)
    else:
        plays = pbp[pbp["epa"].notna() & pbp["posteam"].notna()].copy()
        offense = _side_stats(plays, "posteam", "off")
        defense = _side_stats(plays, "defteam", "def")
        played_stats = offense.merge(defense, on=["team", "game_id"], how="outer")

    # Full team-schedule skeleton -- one row per team per game on its
    # schedule, played or not -- then left-join in the actual per-game
    # stats where they exist. Upcoming games get NaN for their own-game
    # stats (correct: they haven't happened), but still get a row, so
    # _trailing_average (which only looks at *prior* rows) can carry a
    # team's real trailing stats forward into them.
    home_side = schedules[["game_id", "season", "week", "home_team"]].rename(columns={"home_team": "team"})
    away_side = schedules[["game_id", "season", "week", "away_team"]].rename(columns={"away_team": "team"})
    team_schedule = pd.concat([home_side, away_side], ignore_index=True)
    team_game = team_schedule.merge(played_stats, on=["team", "game_id"], how="left")

    value_cols = [c for c in team_game.columns if c.startswith("off_") or c.startswith("def_")]
    team_game = _trailing_average(team_game, group_cols=["team", "season"], order_col="week", value_cols=value_cols)
    feature_cols = [f"{c}_trailing" for c in value_cols]

    # team_game has one row per (team, game_id) -- home and away teams both
    # appear. Renaming "team" to "home_team"/"away_team" and merging on
    # (game_id, home_team) / (game_id, away_team) naturally selects only
    # the row belonging to the actual home/away team for that game, since
    # the merge only matches where the values agree.
    home = team_game[["game_id", "team"] + feature_cols].rename(
        columns={"team": "home_team", **{c: f"home_{c}" for c in feature_cols}}
    )
    away = team_game[["game_id", "team"] + feature_cols].rename(
        columns={"team": "away_team", **{c: f"away_{c}" for c in feature_cols}}
    )

    sched = schedules[[
        "game_id", "season", "week", "game_type", "gameday", "home_team", "away_team",
        "home_score", "away_score", "home_rest", "away_rest", "div_game",
        "roof", "surface", "temp", "wind",
    ]]
    return sched.merge(home, on=["game_id", "home_team"]).merge(away, on=["game_id", "away_team"])


def build_player_td_features(pbp: pd.DataFrame, rosters: pd.DataFrame) -> pd.DataFrame:
    """
    One row per player per game with trailing pre-game features (target
    share, touches/game, red-zone touches/game, historical TD rate, and
    the opponent defense's trailing TD rate allowed to the player's
    position). Also includes same-game context columns (touches,
    targets, anytime_td) needed to derive labels downstream -- those are
    NOT safe to use as model input, only the `*_trailing` columns are.
    """
    rush = pbp[pbp["rusher_player_id"].notna()].copy()
    rec = pbp[pbp["receiver_player_id"].notna()].copy()

    rush_agg = (
        rush.groupby(["rusher_player_id", "game_id", "posteam", "week", "season"])
        .agg(
            rush_touches=("rusher_player_id", "size"),
            rush_redzone_touches=("yardline_100", lambda s: (s <= RED_ZONE_YARDLINE).sum()),
        )
        .reset_index()
        .rename(columns={"rusher_player_id": "player_id"})
    )
    rec_agg = (
        rec.groupby(["receiver_player_id", "game_id", "posteam", "week", "season"])
        .agg(
            targets=("receiver_player_id", "size"),
            receptions=("complete_pass", "sum"),
            rec_redzone_touches=("yardline_100", lambda s: (s <= RED_ZONE_YARDLINE).sum()),
        )
        .reset_index()
        .rename(columns={"receiver_player_id": "player_id"})
    )

    player_game = rush_agg.merge(
        rec_agg, on=["player_id", "game_id", "posteam", "week", "season"], how="outer"
    )
    count_cols = ["rush_touches", "rush_redzone_touches", "targets", "receptions", "rec_redzone_touches"]
    player_game[count_cols] = player_game[count_cols].fillna(0)
    player_game["touches"] = player_game["rush_touches"] + player_game["receptions"]
    player_game["redzone_touches"] = player_game["rush_redzone_touches"] + player_game["rec_redzone_touches"]

    team_targets = rec.groupby(["posteam", "game_id"]).size().rename("team_targets").reset_index()
    player_game = player_game.merge(team_targets, on=["posteam", "game_id"], how="left")
    player_game["target_share"] = player_game["targets"] / player_game["team_targets"]

    scoring_plays = pbp[(pbp["touchdown"] == 1) & pbp["td_player_id"].notna()]
    td_flags = (
        scoring_plays.groupby(["td_player_id", "game_id"])
        .size()
        .rename("anytime_td")
        .reset_index()
        .rename(columns={"td_player_id": "player_id"})
    )
    player_game = player_game.merge(td_flags, on=["player_id", "game_id"], how="left")
    player_game["anytime_td"] = player_game["anytime_td"].fillna(0).clip(upper=1).astype(int)

    roster_cols = (
        rosters[["player_id", "season", "team", "position"]]
        .dropna(subset=["player_id"])
        .drop_duplicates(subset=["player_id", "season"])
    )
    player_game = player_game.merge(roster_cols, on=["player_id", "season"], how="left")
    player_game["team"] = player_game["team"].fillna(player_game["posteam"])

    # Opponent for each team-game, derived from pbp's own home/away columns
    # rather than requiring a schedules argument.
    game_teams = pbp[["game_id", "home_team", "away_team"]].drop_duplicates()
    player_game = player_game.merge(game_teams, on="game_id", how="left")
    player_game["opponent"] = np.where(
        player_game["posteam"] == player_game["away_team"],
        player_game["home_team"],
        player_game["away_team"],
    )
    player_game = player_game.drop(columns=["home_team", "away_team"])

    allowed = (
        player_game.groupby(["opponent", "position", "game_id", "week", "season"])["anytime_td"]
        .sum()
        .rename("td_allowed")
        .reset_index()
        .rename(columns={"opponent": "defteam"})
    )
    allowed = _trailing_average(
        allowed, group_cols=["defteam", "position", "season"], order_col="week", value_cols=["td_allowed"]
    )
    allowed = allowed.rename(columns={
        "defteam": "opponent",
        "td_allowed_trailing": "opponent_position_td_rate_allowed_trailing",
    })
    player_game = player_game.merge(
        allowed[["opponent", "position", "week", "season", "opponent_position_td_rate_allowed_trailing"]],
        on=["opponent", "position", "week", "season"],
        how="left",
    )

    value_cols = ["touches", "redzone_touches", "target_share", "anytime_td"]
    player_game = _trailing_average(
        player_game, group_cols=["player_id", "season"], order_col="week", value_cols=value_cols
    )

    return player_game.drop(columns=["rush_touches", "rush_redzone_touches", "rec_redzone_touches"])


def attach_odds_features(features: pd.DataFrame, odds: list[dict]) -> pd.DataFrame:
    """
    Attach market signal to a `features` DataFrame shaped like
    build_team_game_features's output (needs game_id/home_team/away_team/
    gameday): a no-vig implied home-win probability from the h2h market
    (averaged across bookmakers), plus the median spread_line/total_line.

    `odds` is the same nested list[dict] shape get_current_odds() returns
    (fetched live, not read back from the DB) -- one dict per event with a
    "bookmakers" list of per-market outcomes.

    Matches on (home_team, away_team) after mapping the odds API's full
    team names to nflverse abbreviations via TEAM_NAME_TO_ABBR, with a
    +/-2 day tolerance against `gameday` rather than exact-date equality
    -- `commence_time` is UTC and most evening kickoffs cross midnight UTC
    relative to `gameday` (a local date), so exact string matching would
    miss most primetime games. The tolerance also guards against
    accidentally matching the wrong season if `features` spans more than
    one (an ordered home/away pair is effectively unique within a single
    season under normal NFL scheduling, but not necessarily across years).

    Line movement isn't computed here: it needs multiple snapshots spread
    over real time, and there isn't enough odds_snapshots history
    accumulated yet to make that meaningful.
    """
    rows = []
    for event in odds:
        home_abbr = TEAM_NAME_TO_ABBR.get(event.get("home_team"))
        away_abbr = TEAM_NAME_TO_ABBR.get(event.get("away_team"))
        if not home_abbr or not away_abbr:
            continue

        implied_probs, spreads, totals = [], [], []
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                outcomes = market.get("outcomes", [])
                if market.get("key") == "h2h":
                    prices = {o["name"]: o["price"] for o in outcomes}
                    home_price = prices.get(event.get("home_team"))
                    away_price = prices.get(event.get("away_team"))
                    if home_price is None or away_price is None:
                        continue
                    home_p = _american_to_prob(home_price)
                    away_p = _american_to_prob(away_price)
                    if home_p + away_p > 0:
                        implied_probs.append(home_p / (home_p + away_p))  # no-vig
                elif market.get("key") == "spreads":
                    home_outcome = next((o for o in outcomes if o["name"] == event.get("home_team")), None)
                    if home_outcome and "point" in home_outcome:
                        spreads.append(home_outcome["point"])
                elif market.get("key") == "totals":
                    over_outcome = next((o for o in outcomes if o["name"] == "Over"), None)
                    if over_outcome and "point" in over_outcome:
                        totals.append(over_outcome["point"])

        rows.append({
            "home_team": home_abbr,
            "away_team": away_abbr,
            # tz_localize(None) drops the UTC offset rather than converting
            # to local time -- fine given the day-level tolerance below.
            "commence_date": pd.to_datetime(event.get("commence_time")).tz_localize(None),
            "market_implied_home_win_prob": (sum(implied_probs) / len(implied_probs)) if implied_probs else None,
            "market_spread_line": pd.Series(spreads).median() if spreads else None,
            "market_total_line": pd.Series(totals).median() if totals else None,
            "n_bookmakers": len(event.get("bookmakers", [])),
        })

    odds_cols = ["market_implied_home_win_prob", "market_spread_line", "market_total_line", "n_bookmakers"]
    out = features.copy()

    odds_df = pd.DataFrame(rows)
    if odds_df.empty:
        for col in odds_cols:
            out[col] = None
        return out

    merged = out.merge(odds_df, on=["home_team", "away_team"], how="left")
    merged["date_diff"] = (merged["commence_date"] - pd.to_datetime(merged["gameday"])).abs()

    out_of_tolerance = merged["date_diff"].notna() & (merged["date_diff"] > pd.Timedelta(days=2))
    merged.loc[out_of_tolerance, odds_cols + ["commence_date", "date_diff"]] = None

    merged = merged.sort_values("date_diff").drop_duplicates(subset=["game_id"], keep="first")
    return merged.drop(columns=["commence_date", "date_diff"]).sort_index()


if __name__ == "__main__":
    from src.ingestion.odds import get_current_odds
    from src.ingestion.stats import get_play_by_play, get_rosters, get_schedules

    season = 2025
    print(f"Fetching {season} pbp/schedules/rosters...")
    pbp = get_play_by_play([season])
    schedules = get_schedules([season])
    rosters = get_rosters([season])
    print(f"pbp={pbp.shape} schedules={schedules.shape} rosters={rosters.shape}")

    team_features = build_team_game_features(pbp, schedules)
    print(f"\nteam_game_features: {team_features.shape}")
    trailing_cols = [c for c in team_features.columns if c.endswith("_trailing")]
    week1 = team_features[team_features["week"] == 1][trailing_cols]
    week3 = team_features[team_features["week"] == 3][trailing_cols]
    print(f"week 1 trailing cols all-NaN: {week1.isna().all().all()}")
    print(f"week 3 trailing cols any non-NaN: {week3.notna().any().any()}")

    reg = team_features[team_features["game_type"] == "REG"].dropna(subset=["home_score"])
    reg = reg.assign(home_win=(reg["home_score"] > reg["away_score"]).astype(int))
    epa_diff_ok = reg["home_off_epa_per_play_trailing"].notna()
    if epa_diff_ok.sum() > 0:
        corr = reg.loc[epa_diff_ok, "home_off_epa_per_play_trailing"].corr(reg.loc[epa_diff_ok, "home_win"])
        print(f"corr(home trailing off EPA/play, home win) = {corr:.3f} (positive = sane direction)")

    player_features = build_player_td_features(pbp, rosters)
    print(f"\nplayer_td_features: {player_features.shape}")
    top_touches = player_features.sort_values("touches", ascending=False).head(3)
    print(top_touches[["player_id", "team", "position", "week", "touches", "redzone_touches", "anytime_td"]])

    print("\nFetching live odds + the current (2026) season's schedule...")
    odds = get_current_odds()
    print(f"{len(odds)} events fetched")
    # 2025 pbp has no games in common with live 2026 odds, so exercise
    # attach_odds_features against the real 2026 schedule instead -- no
    # pbp exists yet for 2026 (preseason), so trailing feature columns
    # are absent here; this only verifies the odds join/match logic.
    upcoming = get_schedules([2026])
    with_odds = attach_odds_features(upcoming, odds)
    matched = with_odds["market_implied_home_win_prob"].notna().sum()
    print(f"\nmatched odds onto {matched}/{len(with_odds)} 2026 schedule rows")
    sample = with_odds.dropna(subset=["market_implied_home_win_prob"]).head(3)
    print(sample[["game_id", "home_team", "away_team", "market_implied_home_win_prob", "market_spread_line", "market_total_line"]])
