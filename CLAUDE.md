# Cheech — Personal Betting & News Intelligence App

## Overview
A personal-use app (not for distribution) that ingests NFL data from multiple
sources, predicts game winners and touchdown/prop outcomes, tracks the user's
own bets and their performance over time, and generates a daily curated
newsletter of football news with source citations.

This is a single-user tool. Favor simplicity and local/self-hosted tooling
over multi-tenant, production-grade infrastructure.

## Architecture

Four subsystems, orchestrated primarily via Apache Airflow (user already runs
Airflow for other pipelines):

1. **Ingestion** — pulls stats, news, injury reports, odds, and (optionally)
   social signal into a central datastore.
2. **Prediction** — models for game winners and TD/prop markets, built on
   engineered features from ingested data.
3. **Bet tracking** — a ledger of bets placed, stakes, odds, model
   probabilities at time of bet, and outcomes.
4. **Newsletter** — a daily summarized digest of news + the model's top
   edges, emailed to the user with source citations.
5. **Discord delivery** — event-driven alerts (high-signal news, new
   prediction edges) posted to Discord channels via incoming webhooks, as
   a faster-cadence complement to the daily email.

## Data Sources

### Stats (primary backbone)
- `nfl_data_py` (nflverse) — play-by-play, rosters, injuries, snap counts,
  schedules. Free, well-maintained, first choice for anything structural.

### News
- RSS feeds: ESPN, NFL.com, team beat writers.
- News API (NewsAPI, GNews free tier) filtered by team/player keywords.

### Odds / lines
- The Odds API (free tier available) — current lines and line movement.
  Line movement is a genuinely useful "small signal" feature.

### "Small but maybe not small" signals
- Practice participation reports (DNP/limited/full).
- Weather at game site (any free weather API, keyed to stadium lat/long).
- Snap count trends, target share trends, red zone usage.
- Offensive/defensive coordinator tendencies (situational play-calling rates).

### Social (tweets)
- Flag as the least reliable source: X's API is paid and rate-limited.
- Don't build a hard dependency on it. If pursued, treat as a paid API
  integration decision, not a default assumption. Prioritize beat writers
  and team-affiliated accounts over general chatter.

## Prediction Models

- Start simple: logistic regression or gradient boosting (XGBoost/LightGBM)
  on engineered features. Don't over-engineer before there's a baseline.
- **Game winner**: binary classification on team/matchup-level features
  (EPA, DVOA-style efficiency, rest days, travel, weather).
- **TD scorer / anytime TD**: per-player rate model using red-zone touches,
  historical conversion rate, target share, opponent run/pass defense
  splits.
- **Other props**: model each market on its own natural unit (yards props
  as regression, longest-reception-over/under as a rate model, etc.) rather
  than forcing everything into one model shape.
- Store every prediction with a timestamp and the feature snapshot used to
  generate it, so pre-news vs post-news versions are comparable (e.g.,
  before/after an injury report drops).

## Bet Tracking

Minimal schema (Postgres or SQLite is fine for personal use):

| Field | Notes |
|---|---|
| bet_id | primary key |
| date_placed | |
| market | winner / anytime TD / player prop / etc. |
| selection | team or player + line |
| odds_at_placement | |
| closing_odds | for CLV calculation |
| stake | |
| model_predicted_probability | snapshot at time of bet |
| outcome | win / loss / push |
| notes | |

- Track **closing line value (CLV)** — the gap between odds taken and the
  closing line — as the primary indicator of real edge, not just win/loss
  record. CLV is more predictive of long-run skill than short-term results.
- A lightweight dashboard (`dashboard/app.py`, Streamlit) over this table
  for reviewing what's working, including a real CLV calculation.

## Newsletter

- Daily Airflow task, run each morning during the season.
- Pulls: top news stories of the day + the model's highest-edge picks for
  upcoming games.
- Summarizes with an LLM call; every summarized claim must cite its source
  URL — no uncited claims.
- Delivery: email via SMTP or a free-tier transactional email service
  (e.g., SendGrid free tier) to the user's own address.

## Discord Delivery

A second, faster-cadence delivery channel alongside the daily email —
separate Discord channels/webhooks per content type rather than mixing
markets into one feed:

- **News** (`DISCORD_NEWS_WEBHOOK_URL`): posts on `ingest_news` DAG runs
  (hourly-in-season) when a newly-seen news item matches a high-signal
  keyword filter (injury/roster status). Not every ingested item — the
  daily email already covers the full day's news; this channel is for
  what shouldn't wait until morning.
- **Predictions** (`DISCORD_PREDICTIONS_WEBHOOK_URL`): posts the latest
  run's top model edges when `predict_dag` completes. One channel for
  now, covering the winner model only — a separate TD channel isn't
  worth splitting out until the anytime-TD model is actually wired into
  `predict_dag` (see Open Decisions) and there's real content to post.
- Webhook-only (no persistent bot) — simplest option that fits the
  single-user, self-hosted philosophy. A bot (for on-demand queries like
  "what's my current CLV") is a possible future upgrade, not a v1 need.
- Missing webhook env vars degrade gracefully: the underlying DAG task
  still completes (news ingestion / prediction persistence aren't
  gated on Discord delivery succeeding), just skips the post.

## Engineering Conventions

- **Orchestration**: Airflow DAGs, one per subsystem where practical
  (ingestion DAGs run daily/hourly-in-season; newsletter DAG runs once
  daily; prediction DAG runs ahead of each week's slate).
- **Language**: Python throughout for consistency with existing pipelines.
- **Storage**: prefer boring, local-friendly options (Postgres or SQLite)
  over managed cloud databases unless a real need emerges.
- **Secrets**: API keys (odds, news, email) via environment variables /
  `.env`, never committed.
- **Feature snapshots**: any time a prediction is generated, persist the
  feature vector alongside it — this is what makes later model debugging
  and "what changed" analysis possible.

## Non-Goals

- Not building for other users — no auth system, no multi-tenancy.
- Not chasing a live/real-time tweet firehose as a v1 requirement.
- Not optimizing for scale — optimize for signal quality and for the
  user's ability to review and trust the bet-tracking data.

## Open Decisions (revisit as the project develops)

- Whether to pay for X API access for social signal, or skip it entirely.
- **Resolved:** dashboard framework is Streamlit (`dashboard/app.py`),
  built and in use.
- **Resolved:** anytime-TD is wired into `predict_dag` — `build_player_td_features`
  (`src/models/features.py`) takes an optional `schedules` argument and
  projects one row per (player, upcoming game) for current-roster players
  with real game history this season, giving each their trailing feature
  values (touches, redzone touches, target share, TD rate, opponent's
  trailing TD-rate-allowed to that position). Verified end-to-end against
  real held-out 2025 data (weeks 11+ masked as "upcoming") rather than
  synthetic fixtures, since 2026 has no completed games yet. Discord
  alerting still covers the winner model only — whether TD edges are
  worth their own channel, or folding into the existing predictions
  channel, is still open.
- Prop models beyond winner/anytime-TD: not started.
- **Not live yet:** all 5 DAGs are registered but paused, and no
  Airflow scheduler runs continuously on the user's machine — everything
  built so far (newsletter, Discord delivery) has been verified via
  direct/manual invocation, not a real scheduled run. Revisit once the
  user wants this fully autonomous.
- **Next up:** Discord rich embeds (still plain markdown text), or making
  Airflow live.
