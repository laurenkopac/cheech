"""
Streamlit dashboard for reviewing bet performance and CLV.

Run with: streamlit run dashboard/app.py
"""
import pandas as pd
import streamlit as st

from src.tracking.db import get_engine

st.set_page_config(page_title="Cheech — Bet Tracker", layout="wide")
st.title("Cheech — Bet Tracker")

engine = get_engine()

try:
    bets = pd.read_sql("SELECT * FROM bets", engine)
except Exception:
    bets = pd.DataFrame()

if bets.empty:
    st.info("No bets logged yet. Add rows to the `bets` table to see them here.")
else:
    st.subheader("All Bets")
    st.dataframe(bets, use_container_width=True)

    settled = bets[bets["outcome"].isin(["win", "loss", "push"])]
    if not settled.empty:
        win_rate = (settled["outcome"] == "win").mean()
        st.metric("Win rate", f"{win_rate:.1%}")

    has_clv = bets.dropna(subset=["closing_odds", "odds_at_placement"])
    if not has_clv.empty:
        st.subheader("Closing Line Value")
        st.caption(
            "CLV compares the odds you took to the closing line — "
            "the better long-run indicator of real edge."
        )
        # TODO: implement proper CLV calculation from American/decimal odds
        st.dataframe(
            has_clv[["date_placed", "selection", "odds_at_placement", "closing_odds"]],
            use_container_width=True,
        )
