"""
Bet ledger: log bets as they're placed, patch them with closing odds and
outcomes as those become known, and read them back for CLV/performance
review (see dashboard/app.py).

Unlike the ingestion modules, nothing here is fetched from an external
source -- rows are entered by hand (or by a future betting workflow) and
mutated in place over a bet's lifecycle, so this uses plain INSERT/UPDATE
by bet_id rather than the upsert-by-natural-key pattern in db.py.
"""
from datetime import datetime, timezone

from sqlalchemy import text

VALID_OUTCOMES = ("win", "loss", "push")


def log_bet(
    engine,
    *,
    market: str,
    selection: str,
    odds_at_placement: int,
    stake: float,
    model_predicted_probability: float | None = None,
    notes: str | None = None,
    date_placed: str | None = None,
) -> int:
    """Insert a new bet, pending closing odds and an outcome. Returns the
    new bet_id."""
    date_placed = date_placed or datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO bets (
                    date_placed, market, selection, odds_at_placement,
                    stake, model_predicted_probability, notes
                ) VALUES (
                    :date_placed, :market, :selection, :odds_at_placement,
                    :stake, :model_predicted_probability, :notes
                )
            """),
            {
                "date_placed": date_placed,
                "market": market,
                "selection": selection,
                "odds_at_placement": odds_at_placement,
                "stake": stake,
                "model_predicted_probability": model_predicted_probability,
                "notes": notes,
            },
        )
        return result.lastrowid


def set_closing_odds(engine, bet_id: int, closing_odds: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE bets SET closing_odds = :closing_odds WHERE bet_id = :bet_id"),
            {"closing_odds": closing_odds, "bet_id": bet_id},
        )


def set_outcome(engine, bet_id: int, outcome: str) -> None:
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"outcome must be one of {VALID_OUTCOMES}, got {outcome!r}")
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE bets SET outcome = :outcome WHERE bet_id = :bet_id"),
            {"outcome": outcome, "bet_id": bet_id},
        )


def _american_to_prob(odds: float) -> float:
    """American odds -> implied probability (includes the bookmaker's vig)."""
    if odds > 0:
        return 100 / (odds + 100)
    return -odds / (-odds + 100)


def calculate_clv(odds_at_placement: float, closing_odds: float) -> float:
    """
    Closing line value, in probability points: the gap between the
    closing line's implied probability and the odds actually taken.

    Positive means the closing line implies a *higher* probability than
    what was taken -- the bettor got a cheaper price than the market
    ultimately settled at, i.e. beat the closing line. This is CLAUDE.md's
    primary indicator of real long-run edge, more so than win/loss record,
    since it's assessable immediately rather than waiting on results.
    """
    return _american_to_prob(closing_odds) - _american_to_prob(odds_at_placement)


def get_bets(engine, *, open_only: bool = False) -> list[dict]:
    """All logged bets, most recent first. `open_only` filters to bets
    without a recorded outcome yet."""
    query = "SELECT * FROM bets"
    if open_only:
        query += " WHERE outcome IS NULL"
    query += " ORDER BY date_placed DESC"
    with engine.begin() as conn:
        rows = conn.execute(text(query)).mappings().all()
    return [dict(row) for row in rows]
