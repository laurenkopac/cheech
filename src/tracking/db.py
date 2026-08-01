"""
Thin SQLAlchemy helper for the bet-tracking / predictions / news_items tables.

Usage:
    from src.tracking.db import get_engine, init_db

    engine = get_engine()
    init_db(engine)
"""
import os
from pathlib import Path

from sqlalchemy import create_engine, text
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


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
