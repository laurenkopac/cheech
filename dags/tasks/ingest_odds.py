"""
Task logic for ingest_odds_dag.py. Imports only from src.* (never airflow)
so it can run inside the `cheech` conda env via dags/_env.py -- see that
file's docstring for why the split exists.
"""
from src.ingestion.odds import get_current_odds, persist_odds_snapshot
from src.tracking.db import get_engine, init_db


def run_odds_ingestion():
    engine = get_engine()
    init_db(engine)
    games = get_current_odds()
    n = persist_odds_snapshot(engine, games)
    print(f"Upserted {n} odds snapshot rows for {len(games)} games")


if __name__ == "__main__":
    import sys
    globals()[sys.argv[1]]()
