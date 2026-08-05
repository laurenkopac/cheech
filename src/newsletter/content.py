"""
Pulls real news_items/predictions rows and shapes them into the plain
list[dict] args draft_newsletter() expects (see src/newsletter/summarize.py).
Kept separate from summarize.py so the DB-querying logic is testable
without needing an ANTHROPIC_API_KEY.
"""
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text


def get_recent_news_items(engine, hours: int = 24) -> list[dict]:
    """News items fetched within the last `hours` -- CLAUDE.md's "daily
    curated newsletter" is meant to summarize each day's news, not the
    entire ingested history."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT source, title, url, published_at FROM news_items
                WHERE fetched_at >= :cutoff
                ORDER BY fetched_at DESC
            """),
            {"cutoff": cutoff},
        ).mappings().all()
    return [dict(row) for row in rows]


def get_latest_model_edges(engine, market: str = "winner", top_n: int = 5) -> list[dict]:
    """
    The most recent prediction run's biggest edges: |predicted_probability
    - market_implied_home_win_prob|, largest first. market_implied_*_prob
    comes out of feature_snapshot (attach_odds_features already put it
    there) rather than a separate query -- an "edge" only means something
    relative to what the market thinks, per CLAUDE.md ("deviations from
    [the market] is where edge tends to live").

    Predictions without a usable market probability (e.g. odds weren't
    available yet for that game) are still returned, just sorted last.
    """
    with engine.begin() as conn:
        latest_run = conn.execute(
            text("SELECT MAX(generated_at) FROM predictions WHERE market = :market"),
            {"market": market},
        ).scalar()
        if latest_run is None:
            return []

        rows = conn.execute(
            text("""
                SELECT game_id, subject, predicted_probability, feature_snapshot
                FROM predictions
                WHERE market = :market AND generated_at = :generated_at
            """),
            {"market": market, "generated_at": latest_run},
        ).mappings().all()

    edges = []
    for row in rows:
        snapshot = json.loads(row["feature_snapshot"])
        market_prob = snapshot.get("market_implied_home_win_prob")
        edge = abs(row["predicted_probability"] - market_prob) if market_prob is not None else None
        edges.append({
            "market": market,
            "subject": row["subject"],
            "predicted_probability": row["predicted_probability"],
            "edge": edge,
        })

    # Markets with no attached market-implied probability (e.g. anytime_td,
    # which has no odds join like winner's h2h market does) have edge=None
    # for every row -- fall back to predicted_probability so "top" still
    # means something instead of an arbitrary DB-return order.
    edges.sort(key=lambda e: (e["edge"] is None, -(e["edge"] or 0), -e["predicted_probability"]))
    return edges[:top_n]
