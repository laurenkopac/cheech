# Cheech

Personal NFL data, prediction, bet-tracking, and newsletter app. See
`CLAUDE.md` for the full project brief — that file is the source of truth
for scope and architecture when working with Claude Code on this repo.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# fill in your API keys in .env
```

## Initialize the database

```bash
python -m src.tracking.db
```

## Run ingestion manually (before wiring up Airflow)

```bash
python -m src.ingestion.stats
python -m src.ingestion.news
python -m src.ingestion.odds   # requires ODDS_API_KEY
```

## Run the dashboard

```bash
streamlit run dashboard/app.py
```

## Run Airflow

Point `AIRFLOW_HOME`'s `dags_folder` at this repo's `dags/` directory, or
symlink `dags/` into your existing Airflow install. DAGs:

- `ingest_stats` — daily nflverse pull
- `ingest_news` — hourly RSS/NewsAPI pull
- `ingest_odds` — every 4 hours, for line movement tracking
- `generate_predictions` — weekly, ahead of the slate
- `daily_newsletter` — daily digest with source citations

## Run tests

```bash
pytest
```

## Status

Scaffold stage — ingestion, modeling, and newsletter modules have working
API calls but ingestion-to-database persistence and feature engineering are
marked `TODO`. See `CLAUDE.md` → "Open Decisions" for what's still unsettled.
