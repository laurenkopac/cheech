"""
Streamlit page showing the current week's model predictions across all
markets, replacing "scroll back through Discord alerts" as the way to see
what the models currently think -- Discord stays for the faster-cadence
"something new happened" nudge (CLAUDE.md), this page is for "what's the
full current slate."

Run with: streamlit run dashboard/app.py (this page shows up in the
sidebar automatically -- Streamlit's multipage convention for anything
under dashboard/pages/).
"""
import pandas as pd
import streamlit as st

from src.tracking.db import get_engine
from src.tracking.predictions import MARKETS, get_current_week_label, get_latest_predictions

st.set_page_config(page_title="Cheech — Predictions", layout="wide")

# Same palette as src/newsletter/render.py's MARKET_BADGES and
# src/discord/content.py's MARKET_COLORS (kept as its own copy rather than
# a cross-package import, matching how those two already duplicate this
# palette instead of sharing it) -- so this page reads as the same visual
# system as the email/Discord channels.
MARKET_LABELS = {
    "winner": "Winner",
    "anytime_td": "Anytime TD",
    "first_td": "First TD Scorer",
}
MARKET_BADGE_COLORS = {
    "winner": ("#cffafe", "#0e7490"),
    "anytime_td": ("#dcfce7", "#15803d"),
    "first_td": ("#dcfce7", "#15803d"),
}
DEFAULT_BADGE_COLOR = ("#f4f4f5", "#52525b")


def _badge_html(market: str) -> str:
    bg, fg = MARKET_BADGE_COLORS.get(market, DEFAULT_BADGE_COLOR)
    label = MARKET_LABELS.get(market, market.title())
    return (
        f'<span style="background:{bg}; color:{fg}; padding:4px 12px; '
        f'border-radius:999px; font-size:13px; font-weight:600;">{label}</span>'
    )


def _kickoff_label(gameday) -> str:
    if not gameday or pd.isna(gameday):
        return "TBD"
    return pd.to_datetime(gameday).strftime("%a %b %-d")


engine = get_engine()
predictions_by_market = {market: get_latest_predictions(engine, market) for market in MARKETS}
week_label = get_current_week_label(predictions_by_market)

header_col, refresh_col = st.columns([5, 1])
header_col.title("Predictions")
header_col.caption(week_label or "No predictions generated yet")
if refresh_col.button("Refresh"):
    st.rerun()

if week_label is None:
    st.info(
        "No predictions have been generated yet. Run `predict_dag` (or "
        "`python -m src.models.train`) to populate this week's slate."
    )
    st.stop()

st.markdown(_badge_html("winner"), unsafe_allow_html=True)
winner_df = predictions_by_market["winner"]
if winner_df.empty:
    st.caption("No winner predictions for this week yet.")
else:
    for _, row in winner_df.iterrows():
        away = row["away_team"] if pd.notna(row["away_team"]) else "?"
        home = row["subject"]
        cols = st.columns([3, 2, 2, 2])
        cols[0].markdown(f"**{away} @ {home}**  \n{_kickoff_label(row['gameday'])}")
        cols[1].metric(f"{home} win", f"{row['predicted_probability']:.1%}")
        cols[2].metric(f"{away} win", f"{1 - row['predicted_probability']:.1%}")
        edge = row["edge"]
        cols[3].metric("Edge vs market", f"{edge:.1%}" if pd.notna(edge) else "—")
st.divider()

# TD markets project every player with real touches this season (see
# build_player_td_features), not just skill-position starters -- a game
# can have 30+ rows, most of them long-tail backups at single-digit
# probability. Showing all of them defeats the point of this page (a
# skimmable alternative to scrolling Discord history), so only the top N
# show by default; the rest are one click away rather than gone.
TOP_N_PLAYERS_SHOWN = 8


def _format_display(game_df: pd.DataFrame) -> pd.DataFrame:
    display = (
        game_df[["subject", "predicted_probability"]]
        .rename(columns={"subject": "Player", "predicted_probability": "Probability"})
        .sort_values("Probability", ascending=False)
    )
    display["Probability"] = display["Probability"].map(lambda v: f"{v:.1%}")
    return display


for market in ["anytime_td", "first_td"]:
    st.markdown(_badge_html(market), unsafe_allow_html=True)
    df = predictions_by_market[market]
    if df.empty:
        st.caption("No predictions for this week yet.")
        st.divider()
        continue

    for game_id, game_df in df.groupby("game_id", sort=False):
        away = game_df["away_team"].iloc[0]
        home = game_df["home_team"].iloc[0]
        away = away if pd.notna(away) else "?"
        home = home if pd.notna(home) else "?"
        st.markdown(f"**{away} @ {home}**")

        display = _format_display(game_df)
        st.dataframe(display.head(TOP_N_PLAYERS_SHOWN), use_container_width=True, hide_index=True)
        if len(display) > TOP_N_PLAYERS_SHOWN:
            with st.expander(f"Show all {len(display)} players"):
                st.dataframe(display, use_container_width=True, hide_index=True)
    st.divider()
