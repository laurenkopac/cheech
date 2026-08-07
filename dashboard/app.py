"""
Streamlit dashboard for reviewing bet performance and CLV.

Run with: streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

# `streamlit run` puts this script's own directory (dashboard/) on
# sys.path, not the invoking cwd -- so `from src...` below fails with
# ModuleNotFoundError unless the repo root is added explicitly. Same fix
# as dags/*_dag.py's sys.path.insert for the analogous Airflow issue (see
# dags/_env.py).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from src.tracking.bets import calculate_clv
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
        has_clv = has_clv.copy()
        has_clv["clv"] = has_clv.apply(
            lambda row: calculate_clv(row["odds_at_placement"], row["closing_odds"]), axis=1
        )
        st.metric("Average CLV", f"{has_clv['clv'].mean():+.1%}")

        display = has_clv[["date_placed", "selection", "odds_at_placement", "closing_odds", "clv"]].copy()
        display["clv"] = display["clv"].map(lambda v: f"{v:+.1%}")
        st.dataframe(display, use_container_width=True)
