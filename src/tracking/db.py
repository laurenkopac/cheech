"""
Thin SQLAlchemy helper for the bet-tracking / predictions / news_items tables.

Usage:
    from src.tracking.db import get_engine, init_db

    engine = get_engine()
    init_db(engine)
"""
import os
from pathlib import Path

from sqlalchemy import MetaData, Table, create_engine, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from dotenv import load_dotenv

load_dotenv()

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"


def get_engine():
    db_url = os.environ.get("DATABASE_URL", "sqlite:///cheech.db")
    return create_engine(db_url)


def init_db(engine=None):
    """Create tables if they don't exist. Safe to call repeatedly."""
    engine = engine or get_engine()
    schema_sql = SCHEMA_PATH.read_text()
    with engine.begin() as conn:
        for statement in schema_sql.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))


def upsert_rows(engine, table: str, rows: list[dict], unique_cols: list[str]) -> int:
    """Insert `rows` into `table`, updating in place on conflict.

    `unique_cols` must match a unique/primary key constraint on `table`
    (see sql/schema.sql) -- that's what makes a row a "duplicate" for
    dedup purposes (e.g. news by `url`, stats by their natural key).
    Returns the number of rows written; no-ops on an empty list.
    """
    if not rows:
        return 0

    metadata = MetaData()
    tbl = Table(table, metadata, autoload_with=engine)

    # SQLite caps bound parameters per statement (as low as 999 on older
    # builds) -- batch large upserts so one multi-row INSERT can't exceed it.
    batch_size = max(1, 900 // len(rows[0]))

    with engine.begin() as conn:
        for start in range(0, len(rows), batch_size):
            batch = rows[start:start + batch_size]
            stmt = sqlite_insert(tbl).values(batch)
            update_cols = {c.name: c for c in stmt.excluded if c.name not in unique_cols}
            stmt = stmt.on_conflict_do_update(index_elements=unique_cols, set_=update_cols)
            conn.execute(stmt)

    return len(rows)


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
