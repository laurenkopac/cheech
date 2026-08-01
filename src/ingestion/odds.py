"""
Pulls current lines and (over time, by re-running) line movement from
The Odds API. Free tier is sufficient to start.

Docs: https://the-odds-api.com/liveapi/guides/v4/
"""
import os

import requests

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


if __name__ == "__main__":
    games = get_current_odds()
    print(f"{len(games)} games with odds available")
    if games:
        print(games[0])
