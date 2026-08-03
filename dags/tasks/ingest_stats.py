"""
Task logic for ingest_stats_dag.py. Imports only from src.* (never airflow)
so it can run inside the `cheech` conda env via dags/_env.py -- see that
file's docstring for why the split exists.
"""
from src.ingestion.stats import persist_schedules, persist_injuries, persist_snap_counts
from src.tracking.db import get_engine, init_db

CURRENT_SEASON = 2026


def run_schedules():
    engine = get_engine()
    init_db(engine)
    n = persist_schedules(engine, [CURRENT_SEASON])
    print(f"Upserted {n} schedule rows")


def run_injuries():
    engine = get_engine()
    n = persist_injuries(engine, [CURRENT_SEASON])
    print(f"Upserted {n} injury rows")


def run_snap_counts():
    engine = get_engine()
    n = persist_snap_counts(engine, [CURRENT_SEASON])
    print(f"Upserted {n} snap count rows")


if __name__ == "__main__":
    import sys
    globals()[sys.argv[1]]()
