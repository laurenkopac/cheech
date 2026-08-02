"""
Pulls current lines and (over time, by re-running) line movement from
The Odds API. Free tier is sufficient to start.

Docs: https://the-odds-api.com/liveapi/guides/v4/
"""
import json
import os
from datetime import datetime, timezone

import requests

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


if __name__ == "__main__":
    engine = get_engine()
    init_db(engine)

    games = get_current_odds()
    n = persist_odds_snapshot(engine, games)
    print(f"Upserted {n} odds snapshot rows for {len(games)} games")
