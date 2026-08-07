"""
Entry point / router for the Cheech Streamlit dashboard.

Uses st.navigation (Streamlit >=1.36) instead of the classic
filename-driven pages/ sidebar, so nav labels/icons are explicit
("Bets & P&L", not "app" -- the old sidebar label, derived from this
file's own name, before this rewrite) rather than derived from a
script's filename. st.set_page_config is called here, once, for the
whole app -- individual page scripts must not call it again.

Run with: streamlit run dashboard/app.py
"""
import streamlit as st

st.set_page_config(page_title="Cheech", layout="wide", initial_sidebar_state="expanded")

bets_page = st.Page("pages/2_Bets.py", title="Bets & P&L", icon=":material/payments:", default=True)
predictions_page = st.Page("pages/1_Predictions.py", title="Predictions", icon=":material/bar_chart:")

st.navigation([bets_page, predictions_page]).run()
