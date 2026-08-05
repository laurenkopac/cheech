"""
Pulls current lines and (over time, by re-running) line movement from
The Odds API. Free tier is sufficient to start.

Docs: https://the-odds-api.com/liveapi/guides/v4/
"""
import json
import os
from datetime import datetime, timezone

import pandas as pd
import requests
from sqlalchemy import text

from src.tracking.db import get_engine, init_db, upsert_rows

BASE_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"


def get_current_odds(markets: str = "h2h,spreads,totals") -> list[dict]:
    api_key = os.environ.get("ODDS_API_KEY")
    if not api_key:
        raise RuntimeError("ODDS_API_KEY not set")
    resp = requests.get(
        BASE_URL,
        params={
            "apiKey": api_key,
            "regions": "us",
            "markets": markets,
            "oddsFormat": "american",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def persist_odds_snapshot(engine, games: list[dict]) -> int:
    """Flatten each game's per-bookmaker markets into one row apiece and
    append them as a timestamped snapshot.

    Deliberately not deduped/overwritten like stats or news: line
    movement is the point, so every fetch must land as new rows rather
    than collapsing onto the latest line.
    """
    fetched_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for game in games:
        for bookmaker in game.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                rows.append({
                    "event_id": game.get("id"),
                    "commence_time": game.get("commence_time"),
                    "home_team": game.get("home_team"),
                    "away_team": game.get("away_team"),
                    "bookmaker": bookmaker.get("key"),
                    "market": market.get("key"),
                    "raw_json": json.dumps(market),
                    "fetched_at": fetched_at,
                })
    return upsert_rows(engine, "odds_snapshots", rows, unique_cols=["event_id", "bookmaker", "market", "fetched_at"])


def get_closing_odds_for_games(engine, schedules: pd.DataFrame) -> list[dict]:
    """
    Reconstruct each event's closing line -- the most recent odds_snapshot
    fetch for that event no later than kickoff -- from persisted history,
    in the same nested list[dict] shape get_current_odds() returns (one
    dict per event, home_team/away_team as the Odds API's own full names,
    bookmakers -> markets -> outcomes). That means attach_odds_features
    works identically whether it's given live or historical odds -- no
    separate matching/name-mapping logic needed here, including which
    events actually correspond to a played game in `schedules`: that's
    left entirely to attach_odds_features's existing team-name/date
    matching, rather than duplicated here against odds_snapshots' own
    Odds-API event_id (which has no direct join key to nflverse's game_id).
    Returns events for any game with recorded snapshot history, played or
    not -- callers combining this with live odds (see build_features)
    should only use it to fill gaps live odds didn't cover, since live
    data should always win for a genuinely upcoming game.

    Unlike get_current_odds() (which only ever covers currently-listed,
    not-yet-played games), this is what makes market_spread_line/
    market_total_line -- and anything derived from them, like
    build_player_td_features's team_implied_total -- possible for
    real/historical training rows at all, since the Odds API itself has no
    way to look up a past game's line after the fact. Only as good as
    however much odds_snapshots has actually accumulated, though: this
    requires ingest_odds_dag to have actually been running (or repeated
    manual invocation) before a game's kickoff -- a game with no snapshot
    fetched before it started just isn't in the returned list, same as
    attach_odds_features's existing "just leave it NaN" tolerance for any
    other unmatched game.

    `schedules` is only used as a cheap "is there any played game at all
    this season" fast-path -- skips querying odds_snapshots entirely for a
    season with nothing played yet (e.g. preseason), since none of this
    could help build_features fill anything in yet either way.
    """
    if schedules["home_score"].isna().all():
        return []

    with engine.begin() as conn:
        snapshots = pd.read_sql(text("SELECT * FROM odds_snapshots"), conn)
    if snapshots.empty:
        return []

    snapshots["commence_time"] = pd.to_datetime(snapshots["commence_time"], utc=True)
    snapshots["fetched_at"] = pd.to_datetime(snapshots["fetched_at"], utc=True)

    before_kickoff = snapshots[snapshots["fetched_at"] <= snapshots["commence_time"]]
    if before_kickoff.empty:
        return []

    closing_fetched_at = before_kickoff.groupby("event_id")["fetched_at"].transform("max")
    closing = before_kickoff[before_kickoff["fetched_at"] == closing_fetched_at]

    events = []
    for event_id, group in closing.groupby("event_id"):
        first = group.iloc[0]
        bookmakers: dict[str, dict] = {}
        for _, row in group.iterrows():
            bookmaker = bookmakers.setdefault(row["bookmaker"], {"key": row["bookmaker"], "markets": []})
            bookmaker["markets"].append(json.loads(row["raw_json"]))
        events.append({
            "id": event_id,
            "home_team": first["home_team"],
            "away_team": first["away_team"],
            "commence_time": first["commence_time"].isoformat(),
            "bookmakers": list(bookmakers.values()),
        })
    return events


if __name__ == "__main__":
    engine = get_engine()
    init_db(engine)

    games = get_current_odds()
    n = persist_odds_snapshot(engine, games)
    print(f"Upserted {n} odds snapshot rows for {len(games)} games")
