-- Cheech schema (SQLite). init_db() executes one CREATE TABLE statement
-- at a time, so keep each statement self-contained.
--
-- Tables below hold a few structured columns for filtering/joins, plus a
-- raw_json column with the full source row -- nflverse/news schemas shift
-- occasionally and this avoids brittle column-by-column mapping.

CREATE TABLE IF NOT EXISTS schedules (
    game_id TEXT PRIMARY KEY,
    season INTEGER NOT NULL,
    week INTEGER,
    game_type TEXT,
    gameday TEXT,
    home_team TEXT,
    away_team TEXT,
    home_score REAL,
    away_score REAL,
    raw_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS injuries (
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    team TEXT NOT NULL,
    gsis_id TEXT NOT NULL,
    full_name TEXT,
    position TEXT,
    report_status TEXT,
    practice_status TEXT,
    raw_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (season, week, team, gsis_id)
);

CREATE TABLE IF NOT EXISTS snap_counts (
    game_id TEXT NOT NULL,
    pfr_player_id TEXT NOT NULL,
    player TEXT,
    team TEXT,
    position TEXT,
    offense_pct REAL,
    defense_pct REAL,
    st_pct REAL,
    raw_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (game_id, pfr_player_id)
);

CREATE TABLE IF NOT EXISTS news_items (
    url TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT,
    published_at TEXT,
    fetched_at TEXT NOT NULL
);

-- Unlike the tables above, this is append-only: every fetch is a new
-- timestamped snapshot, not an upsert of the "latest" line. Line movement
-- (and CLV, computed against it) only exists if every snapshot survives.
CREATE TABLE IF NOT EXISTS odds_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    commence_time TEXT,
    home_team TEXT,
    away_team TEXT,
    bookmaker TEXT NOT NULL,
    market TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    UNIQUE (event_id, bookmaker, market, fetched_at)
);

CREATE INDEX IF NOT EXISTS idx_odds_snapshots_event
    ON odds_snapshots (event_id, bookmaker, market, fetched_at);

-- User-entered, not pulled from a source -- rows are created at bet time
-- and mutated in place (closing_odds once the line closes, outcome once
-- the game finishes), rather than upserted or appended.
CREATE TABLE IF NOT EXISTS bets (
    bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_placed TEXT NOT NULL,
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    odds_at_placement INTEGER NOT NULL,
    closing_odds INTEGER,
    stake REAL NOT NULL,
    model_predicted_probability REAL,
    outcome TEXT CHECK (outcome IN ('win', 'loss', 'push') OR outcome IS NULL),
    notes TEXT
);

-- Append-only, like odds_snapshots: every generation run is a new row, not
-- an upsert of the "latest" prediction. feature_snapshot is the exact
-- feature vector used, so a pre-news and post-news prediction for the
-- same game stay independently comparable (CLAUDE.md).
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    market TEXT NOT NULL,
    game_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    predicted_probability REAL NOT NULL,
    feature_snapshot TEXT NOT NULL,
    UNIQUE (generated_at, market, game_id, subject)
);
