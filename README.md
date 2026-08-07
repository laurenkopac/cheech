# Cheech

Personal NFL data, prediction, bet-tracking, and newsletter app. See
`CLAUDE.md` for the full project brief — that file is the source of truth
for scope and architecture when working with Claude Code on this repo.

## Setup

This repo needs Python 3.10/3.11 — `nfl_data_py` pins `pandas<2.0`, which
has no prebuilt wheel for Python 3.12+. If your system Python is 3.12
(e.g. current Homebrew `python3`), a plain `venv` will fail to install
`pandas`. A conda env pinned to 3.11 is the path of least resistance if
you don't already have an older Python available:

```bash
conda create -n cheech python=3.11 -y
conda activate cheech
pip install -r requirements.txt

# xgboost specifically: install via conda-forge, not pip. Pip's wheel
# needs a separate `brew install libomp` on macOS, and mixing pip/conda
# installs of xgboost has caused corrupted, version-mismatched native
# libraries in practice — if it ever breaks, purge both pip's and
# conda's copies and reinstall clean from conda-forge.
conda install -c conda-forge xgboost -y

cp .env.example .env
# fill in your API keys in .env
```

If your system Python is already 3.10/3.11, a normal venv works fine:

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
- `ingest_news` — hourly RSS/NewsAPI pull; also posts high-signal
  (injury/roster) items to Discord if `DISCORD_NEWS_WEBHOOK_URL` is set
- `ingest_odds` — every 4 hours, for line movement tracking
- `generate_predictions` — weekly, ahead of the slate; also posts the
  latest run's top edges to Discord if `DISCORD_PREDICTIONS_WEBHOOK_URL`
  is set
- `daily_newsletter` — daily digest with source citations

All 5 DAGs are registered but currently **paused**, and no scheduler is
running continuously on this machine — nothing fires on its own yet.
Unpause with `airflow dags unpause <dag_id>` and start `airflow scheduler`
(or `airflow standalone`) when ready for real scheduled runs; until then,
every task has instead been run/verified manually (see Status below).

## Run tests

No automated test suite yet (`pytest` is in `requirements.txt` for when
one exists) — every module so far has instead been verified by actually
running it against real data (live API pulls, a real SQLite DB) rather
than mocked fixtures. See each module's `if __name__ == "__main__":`
block for a runnable example.

## Status

Ingestion (stats/news/odds), the bet ledger, feature engineering, and
winner-model prediction are built, wired into their Airflow DAGs, and
verified end-to-end against real data. The Streamlit dashboard shows
real bets with a working closing-line-value (CLV) calculation.

The newsletter is fully wired and verified end-to-end: real news +
model-edge queries, real LLM summarization (Anthropic), and delivery via
Gmail SMTP. The email body is rendered from the LLM's markdown draft to
styled HTML (`src/newsletter/send.py`), with the raw markdown kept as a
plain-text fallback part.

Discord delivery is also wired and verified end-to-end, as a
faster-cadence complement to the daily email: `ingest_news` posts
high-signal (injury/roster) news items as they're found, and
`generate_predictions` posts the latest run's top edges — each to its
own channel via a separate webhook (`src/discord/`). See CLAUDE.md →
"Discord Delivery" for the design.

**Not live yet** — see "Run Airflow" above. Everything so far has been
verified via direct/manual invocation, not a running scheduler.

The winner, anytime-TD, and first-TD-scorer models are all wired into
`generate_predictions` now — `build_player_td_features` projects one row
per (player, upcoming game) for current-roster players with real game
history this season (see its docstring). First-TD reuses anytime-TD's
model/features but normalizes predicted probabilities to sum to 1 within
each game, since only one player actually scores first. Verified
end-to-end against real held-out 2025 data (weeks 11+ masked as
"upcoming"); real 2026 predictions won't exist until completed games
accumulate this season. Prop markets beyond winner/anytime-TD/first-TD
haven't been started.

See `sql/schema.sql` for the current schema (schedules, injuries,
snap_counts, news_items, odds_snapshots, bets, predictions) and
`CLAUDE.md` → "Open Decisions" for what's still unsettled.
