"""
Streamlit page showing the current week's model predictions across all
markets, replacing "scroll back through Discord alerts" as the way to see
what the models currently think -- Discord stays for the faster-cadence
"something new happened" nudge (CLAUDE.md), this page is for "what's the
full current slate."

Visual design is a dark "prediction terminal" register (stadium-at-night
charcoal, tabular mono numerals) rather than Streamlit's default light
theme -- see the field-position bar in `_winner_card_html` below, which
renders win probability as a ball position on a 100-yard bar instead of a
generic progress bar. Winner/TD accent colors still match the newsletter's
CATEGORY_COLORS/MARKET_BADGES and Discord's MARKET_COLORS (brightened for
a dark background), so this page reads as the same cross-channel system,
just restyled for its own medium.

Run with: streamlit run dashboard/app.py (this page shows up in the
sidebar automatically -- Streamlit's multipage convention for anything
under dashboard/pages/).
"""
import re
import sys
from pathlib import Path

# Same sys.path fix as dashboard/app.py -- streamlit only puts this
# script's own directory (dashboard/pages/) on sys.path, not the repo
# root, and pages run independently enough that app.py's fix can't be
# relied on to have already applied.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import streamlit as st

from src.tracking.db import get_engine
from src.tracking.predictions import MARKETS, get_current_week_label, get_latest_predictions

st.set_page_config(page_title="Cheech — Predictions", layout="wide")

# ---------------------------------------------------------------- tokens --
INK = "#10171A"
PANEL = "#1A2327"
PANEL_RAISED = "#212B30"
HAIRLINE = "#2C3A3F"
CHALK = "#ECF2F1"
SLATE = "#7E939A"
CYAN = "#38D6DC"
GREEN = "#34D399"
AMBER = "#F2A93B"

MARKET_LABELS = {
    "winner": "Winner",
    "anytime_td": "Anytime TD",
    "first_td": "First TD Scorer",
}
MARKET_ACCENT = {"winner": CYAN, "anytime_td": GREEN, "first_td": GREEN}
DEFAULT_ACCENT = SLATE

TOP_N_PLAYERS_SHOWN = 8
_SUBJECT_RE = re.compile(r"^(.*)\s\(([^)]+)\)$")

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

    [data-testid="stDecoration"] {{ display: none; }}
    .stApp {{ background: {INK}; }}
    [data-testid="stHeader"] {{ background: {INK}; }}
    [data-testid="stHeader"] svg {{ fill: {SLATE}; }}
    [data-testid="stToolbar"] {{ background: {INK}; }}
    [data-testid="stSidebar"] {{ background: {PANEL}; border-right: 1px solid {HAIRLINE}; }}
    [data-testid="stSidebar"] * {{ color: {SLATE} !important; }}
    .block-container {{ padding-top: 3.5rem; max-width: 1100px; }}
    /* Body font via inheritance only -- a blanket ".stApp span/div" rule
       out-specifies Streamlit's own icon-font class (e.g. the expander's
       arrow glyph), turning it into literal ligature text like
       "keyboard_arrow_right" instead of an arrow. */
    .stApp {{ font-family: 'IBM Plex Sans', sans-serif; }}

    .cp-title {{
        font-family: 'Anton', sans-serif; font-size: 2.6rem; letter-spacing: 0.02em;
        color: {CHALK}; text-transform: uppercase; margin: 0; line-height: 1;
    }}
    .cp-subtitle {{
        font-family: 'IBM Plex Mono', monospace; color: {SLATE}; letter-spacing: 0.14em;
        font-size: 0.8rem; text-transform: uppercase; margin: 0.5rem 0 0 0;
    }}
    .cp-section {{
        font-family: 'IBM Plex Mono', monospace; letter-spacing: 0.2em; text-transform: uppercase;
        font-size: 0.75rem; font-weight: 600; margin: 2.4rem 0 1rem 0; padding-bottom: 0.6rem;
        border-bottom: 1px solid {HAIRLINE}; display: flex; align-items: center; gap: 0.6rem;
    }}
    .cp-dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
    .cp-empty {{
        font-family: 'IBM Plex Mono', monospace; color: {SLATE}; font-size: 0.85rem;
        padding: 0.6rem 0 1.2rem 0;
    }}

    .cp-card {{
        background: {PANEL}; border: 1px solid {HAIRLINE}; border-radius: 6px;
        padding: 1.1rem 1.4rem; margin-bottom: 0.75rem;
    }}
    .cp-card-head {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.9rem; }}
    .cp-matchup {{ font-weight: 600; color: {CHALK}; font-size: 0.95rem; }}
    .cp-at {{ color: {SLATE}; font-weight: 400; }}
    .cp-kickoff {{ font-family: 'IBM Plex Mono', monospace; color: {SLATE}; font-size: 0.72rem; letter-spacing: 0.08em; }}

    .cp-field {{ display: flex; align-items: center; }}
    .cp-endzone {{ display: flex; flex-direction: column; align-items: center; width: 64px; flex-shrink: 0; }}
    .cp-team {{ font-family: 'IBM Plex Sans', sans-serif; font-weight: 600; font-size: 0.72rem; color: {SLATE}; letter-spacing: 0.04em; }}
    .cp-pct {{ font-family: 'Anton', sans-serif; font-size: 1.5rem; color: {CHALK}; line-height: 1.15; }}
    .cp-endzone-home {{ flex-direction: column-reverse; }}

    .cp-bar {{ position: relative; flex: 1; height: 6px; margin: 0 1.1rem; background: {HAIRLINE}; border-radius: 3px; }}
    .cp-tick {{ position: absolute; top: -3px; width: 1px; height: 12px; background: rgba(236,242,241,0.16); }}
    .cp-midfield {{ position: absolute; left: 50%; top: -5px; width: 1px; height: 16px; background: rgba(236,242,241,0.4); }}
    .cp-fill {{ position: absolute; top: 0; height: 6px; border-radius: 3px; }}
    .cp-ball {{ position: absolute; top: 50%; width: 12px; height: 12px; border-radius: 50%; transform: translate(-50%, -50%); }}

    .cp-edge {{
        font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; letter-spacing: 0.14em; color: {SLATE};
        text-transform: uppercase; margin-top: 0.9rem; padding-top: 0.7rem; border-top: 1px solid {HAIRLINE};
    }}
    .cp-edge-value {{ color: {CHALK}; }}

    .cp-game-label {{
        font-family: 'IBM Plex Sans', sans-serif; font-weight: 600; color: {CHALK}; font-size: 0.85rem;
        margin: 1.2rem 0 0.5rem 0;
    }}
    .cp-table {{ border: 1px solid {HAIRLINE}; border-radius: 6px; overflow: hidden; }}
    .cp-row {{
        display: flex; justify-content: space-between; align-items: center; padding: 0.55rem 1rem;
        background: {PANEL}; border-bottom: 1px solid {HAIRLINE};
    }}
    .cp-row:last-child {{ border-bottom: none; }}
    .cp-row-top {{ border-left: 3px solid var(--accent); padding-left: calc(1rem - 3px); }}
    .cp-player {{ color: {CHALK}; font-size: 0.85rem; }}
    .cp-player-team {{ color: {SLATE}; font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem; margin-left: 0.4rem; }}
    .cp-prob {{ font-family: 'IBM Plex Mono', monospace; font-variant-numeric: tabular-nums; color: {CHALK}; font-size: 0.85rem; }}

    [data-testid="stButton"] button {{
        background: {PANEL_RAISED}; color: {SLATE}; border: 1px solid {HAIRLINE}; border-radius: 4px;
        font-family: 'IBM Plex Mono', monospace; letter-spacing: 0.1em; text-transform: uppercase; font-size: 0.72rem;
    }}
    [data-testid="stButton"] button:hover {{ border-color: {CYAN}; color: {CYAN}; }}

    [data-testid="stExpander"] {{ background: {PANEL}; border: 1px solid {HAIRLINE}; border-radius: 6px; margin-top: 0.4rem; }}
    [data-testid="stExpander"] summary {{
        font-family: 'IBM Plex Mono', monospace; color: {SLATE} !important; font-size: 0.72rem;
        letter-spacing: 0.08em; text-transform: uppercase;
    }}

    [data-testid="stAlert"] {{ background: {PANEL}; border: 1px solid {HAIRLINE}; border-radius: 6px; }}
    [data-testid="stAlert"] p {{ color: {SLATE} !important; font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def _kickoff_label(gameday) -> str:
    if not gameday or pd.isna(gameday):
        return "TBD"
    return pd.to_datetime(gameday).strftime("%a · %b %-d").upper()


def _split_subject(subject: str) -> tuple[str, str]:
    match = _SUBJECT_RE.match(subject or "")
    return (match.group(1), match.group(2)) if match else (subject or "", "")


def _section_header(market: str) -> str:
    return (
        f'<div class="cp-section"><span class="cp-dot" style="background:{MARKET_ACCENT.get(market, DEFAULT_ACCENT)};">'
        f'</span>{MARKET_LABELS.get(market, market.title())}</div>'
    )


def _winner_card_html(row) -> str:
    away = row["away_team"] if pd.notna(row["away_team"]) else "?"
    home = row["subject"]
    home_pct = row["predicted_probability"]
    away_pct = 1 - home_pct
    ball_left = home_pct * 100
    edge = row["edge"]
    edge_label = f"{edge:.1%}" if pd.notna(edge) else "—"

    ticks = "".join(f'<div class="cp-tick" style="left:{t}%;"></div>' for t in range(10, 100, 10))
    fill_left, fill_width = (50, ball_left - 50) if ball_left >= 50 else (ball_left, 50 - ball_left)

    return f"""
    <div class="cp-card">
      <div class="cp-card-head">
        <span class="cp-matchup">{away} <span class="cp-at">@</span> {home}</span>
        <span class="cp-kickoff">{_kickoff_label(row['gameday'])}</span>
      </div>
      <div class="cp-field">
        <div class="cp-endzone"><span class="cp-team">{away}</span><span class="cp-pct">{away_pct:.1%}</span></div>
        <div class="cp-bar">
          {ticks}
          <div class="cp-midfield"></div>
          <div class="cp-fill" style="left:{fill_left}%; width:{fill_width}%; background:{CYAN};"></div>
          <div class="cp-ball" style="left:{ball_left:.1f}%; background:{CYAN}; box-shadow:0 0 0 4px rgba(56,214,220,0.18);"></div>
        </div>
        <div class="cp-endzone cp-endzone-home"><span class="cp-team">{home}</span><span class="cp-pct">{home_pct:.1%}</span></div>
      </div>
      <div class="cp-edge">Edge vs market <span class="cp-edge-value">{edge_label}</span></div>
    </div>
    """


def _player_table_html(game_df: pd.DataFrame, accent: str, limit: int = None) -> str:
    ranked = game_df.sort_values("predicted_probability", ascending=False)
    if limit is not None:
        ranked = ranked.head(limit)
    rows = []
    for i, (_, row) in enumerate(ranked.iterrows()):
        name, team = _split_subject(row["subject"])
        top_class = " cp-row-top" if i == 0 else ""
        style = f' style="--accent:{accent};"' if i == 0 else ""
        rows.append(
            f'<div class="cp-row{top_class}"{style}>'
            f'<span class="cp-player">{name}<span class="cp-player-team">{team}</span></span>'
            f'<span class="cp-prob">{row["predicted_probability"]:.1%}</span>'
            f"</div>"
        )
    return f'<div class="cp-table">{"".join(rows)}</div>'


engine = get_engine()
predictions_by_market = {market: get_latest_predictions(engine, market) for market in MARKETS}
week_label = get_current_week_label(predictions_by_market)

header_col, refresh_col = st.columns([5, 1])
header_col.markdown('<div class="cp-title">Predictions</div>', unsafe_allow_html=True)
header_col.markdown(f'<div class="cp-subtitle">{(week_label or "No slate yet").upper()}</div>', unsafe_allow_html=True)
with refresh_col:
    st.write("")
    if st.button("Refresh"):
        st.rerun()

if week_label is None:
    st.info(
        "No predictions have been generated yet. Run `predict_dag` (or "
        "`python -m src.models.train`) to populate this week's slate."
    )
    st.stop()

st.markdown(_section_header("winner"), unsafe_allow_html=True)
winner_df = predictions_by_market["winner"]
if winner_df.empty:
    st.markdown('<div class="cp-empty">No winner predictions for this week yet.</div>', unsafe_allow_html=True)
else:
    for _, row in winner_df.iterrows():
        st.markdown(_winner_card_html(row), unsafe_allow_html=True)

for market in ["anytime_td", "first_td"]:
    st.markdown(_section_header(market), unsafe_allow_html=True)
    df = predictions_by_market[market]
    if df.empty:
        st.markdown('<div class="cp-empty">No predictions for this week yet.</div>', unsafe_allow_html=True)
        continue

    accent = MARKET_ACCENT.get(market, DEFAULT_ACCENT)
    for game_id, game_df in df.groupby("game_id", sort=False):
        away = game_df["away_team"].iloc[0]
        home = game_df["home_team"].iloc[0]
        away = away if pd.notna(away) else "?"
        home = home if pd.notna(home) else "?"
        st.markdown(f'<div class="cp-game-label">{away} @ {home}</div>', unsafe_allow_html=True)
        st.markdown(_player_table_html(game_df, accent, limit=TOP_N_PLAYERS_SHOWN), unsafe_allow_html=True)
        if len(game_df) > TOP_N_PLAYERS_SHOWN:
            with st.expander(f"Show all {len(game_df)} players"):
                st.markdown(_player_table_html(game_df, accent), unsafe_allow_html=True)
