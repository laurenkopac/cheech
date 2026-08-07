"""
Bets & P&L page -- the bet ledger (src/tracking/bets.py) restyled into
the same dark "sleek modern" system as the Predictions page (see
dashboard/theme.py), with its own signature: bet rows rendered as
sportsbook ticket stubs (a perforated divider between the bet's terms and
its settled result), and cumulative P&L as a status-colored area chart
(profit green / loss red around a zero baseline) rather than a generic
KPI-tile-plus-sparkline hero.

CLAUDE.md flags closing line value (CLV), not raw win/loss record, as
the real long-run skill indicator -- the scoreboard strip below leads
with Record and P&L (what a bettor asks first) but keeps Avg CLV
alongside them at equal weight, not buried.

Run via dashboard/app.py's st.navigation -- this file must NOT call
st.set_page_config itself (already called once there).
"""
import sys
from pathlib import Path

# streamlit only puts this script's own directory (dashboard/pages/) on
# sys.path, not the repo root -- needed for `from src...` below.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.theme import BORDER, CHALK, CRITICAL, GOOD, INK, MUTED, PANEL_RAISED, SLATE, inject_base_css
from src.tracking.bets import calculate_clv, calculate_profit, get_bets
from src.tracking.db import get_engine

inject_base_css()

GRID = "rgba(244,246,248,0.06)"

st.markdown(
    f"""
    <style>
    .cp-scoreboard {{ display: flex; }}
    .cp-stat {{ flex: 1; padding: 0 1.5rem; border-left: 1px solid {BORDER}; }}
    .cp-stat:first-child {{ border-left: none; padding-left: 0; }}
    .cp-stat-label {{
        font-family: 'IBM Plex Mono', monospace; font-size: 0.66rem; letter-spacing: 0.12em;
        text-transform: uppercase; color: {SLATE}; margin-bottom: 0.4rem;
    }}
    .cp-stat-value {{ font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 1.5rem; color: {CHALK}; }}
    .cp-positive {{ color: {GOOD}; }}
    .cp-negative {{ color: {CRITICAL}; }}

    .cp-ticket {{
        display: flex; align-items: stretch; background: {PANEL_RAISED}; border: 1px solid {BORDER};
        border-radius: 12px; margin-bottom: 0.6rem; overflow: hidden;
    }}
    .cp-ticket-main {{ flex: 1; padding: 0.9rem 1.2rem; }}
    .cp-ticket-selection {{ font-family: 'Inter', sans-serif; font-weight: 600; color: {CHALK}; font-size: 0.9rem; }}
    .cp-ticket-market {{
        font-family: 'IBM Plex Mono', monospace; font-size: 0.62rem; color: {SLATE}; margin-left: 0.5rem;
        text-transform: uppercase; letter-spacing: 0.07em;
    }}
    .cp-ticket-meta {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem; color: {SLATE}; margin-top: 0.35rem; }}
    .cp-ticket-perf {{ border-left: 2px dashed {BORDER}; margin: 0.7rem 0; }}
    .cp-ticket-result {{
        display: flex; flex-direction: column; align-items: flex-end; justify-content: center; gap: 0.4rem;
        padding: 0.9rem 1.3rem; min-width: 108px;
    }}
    .cp-pill {{
        font-family: 'IBM Plex Mono', monospace; font-size: 0.62rem; font-weight: 700; letter-spacing: 0.08em;
        padding: 3px 9px; border-radius: 999px; color: {INK};
    }}
    .cp-pill-good {{ background: {GOOD}; }}
    .cp-pill-critical {{ background: {CRITICAL}; }}
    .cp-pill-neutral {{ background: {MUTED}; color: {CHALK}; }}
    .cp-pill-open {{ background: transparent; border: 1px solid {BORDER}; color: {SLATE}; }}
    .cp-ticket-profit {{ font-family: 'IBM Plex Mono', monospace; font-weight: 600; font-size: 0.85rem; color: {CHALK}; }}
    </style>
    """,
    unsafe_allow_html=True,
)

_PILL = {
    "win": ("cp-pill-good", "WIN"),
    "loss": ("cp-pill-critical", "LOSS"),
    "push": ("cp-pill-neutral", "PUSH"),
}


def _american_label(odds) -> str:
    return f"{int(odds):+d}" if pd.notna(odds) else "—"


def _ticket_html(row) -> str:
    outcome = row["outcome"]
    pill_class, pill_label = _PILL.get(outcome, ("cp-pill-open", "OPEN"))
    profit = row.get("profit")
    profit_label = f"{profit:+,.2f}" if pd.notna(profit) else "—"
    date_label = pd.to_datetime(row["date_placed"]).strftime("%b %-d, %Y") if pd.notna(row["date_placed"]) else "—"

    return f"""
    <div class="cp-ticket">
      <div class="cp-ticket-main">
        <span class="cp-ticket-selection">{row['selection']}</span>
        <span class="cp-ticket-market">{row['market']}</span>
        <div class="cp-ticket-meta">{date_label} · Odds {_american_label(row['odds_at_placement'])} · Stake ${row['stake']:,.2f}</div>
      </div>
      <div class="cp-ticket-perf"></div>
      <div class="cp-ticket-result">
        <span class="cp-pill {pill_class}">{pill_label}</span>
        <span class="cp-ticket-profit">{profit_label}</span>
      </div>
    </div>
    """


def _pnl_chart(settled: pd.DataFrame) -> alt.Chart:
    df = settled.sort_values("date_placed").copy()
    df["cumulative"] = df["profit"].cumsum()
    df["pos"] = df["cumulative"].clip(lower=0)
    df["neg"] = df["cumulative"].clip(upper=0)

    nearest = alt.selection_point(nearest=True, on="pointerover", fields=["date_placed"], empty=False)

    base = alt.Chart(df).encode(x=alt.X("date_placed:T", title=None))

    # step-after, not a smooth curve -- a bettor's bankroll actually jumps at
    # each settled bet, not drifts continuously between them, and a step
    # reads that discreteness honestly instead of implying a trend between points.
    area_pos = base.mark_area(opacity=0.16, color=GOOD, line=False, interpolate="step-after").encode(
        y=alt.Y("pos:Q", title=None, axis=alt.Axis(format="+$,.0f", grid=True, gridColor=GRID, domain=False, tickColor="transparent", labelColor=SLATE, labelFont="IBM Plex Mono", labelFontSize=10))
    )
    area_neg = base.mark_area(opacity=0.16, color=CRITICAL, line=False, interpolate="step-after").encode(y=alt.Y("neg:Q", axis=None))
    baseline = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=BORDER, strokeWidth=1).encode(y="y:Q")
    line = base.mark_line(strokeWidth=2, color=CHALK, interpolate="step-after").encode(y=alt.Y("cumulative:Q", axis=None))

    selectors = base.mark_point(opacity=0).encode(y="cumulative:Q").add_params(nearest)
    points = line.mark_point(size=70, filled=True, color=CHALK).encode(
        opacity=alt.condition(nearest, alt.value(1), alt.value(0))
    )
    rule = base.mark_rule(color=BORDER).transform_filter(nearest)
    label = line.mark_text(align="left", dx=10, dy=-10, color=CHALK, font="IBM Plex Mono", fontSize=12).encode(
        text=alt.condition(nearest, alt.Text("cumulative:Q", format="+$,.0f"), alt.value(""))
    )

    return (
        alt.layer(area_pos, area_neg, baseline, line, selectors, points, rule, label)
        .properties(height=240, background="transparent")
        .configure_view(strokeWidth=0)
        .configure_axisX(domain=False, grid=False, tickColor="transparent", labelColor=SLATE, labelFont="IBM Plex Mono", labelFontSize=10)
    )


engine = get_engine()
bets = pd.DataFrame(get_bets(engine))

st.markdown('<div class="cp-title">Bets &amp; P&amp;L</div>', unsafe_allow_html=True)
st.markdown('<div class="cp-subtitle">Ledger &amp; performance</div>', unsafe_allow_html=True)

if bets.empty:
    st.info("No bets logged yet. Add rows to the `bets` table to see your record and P&L here.")
    st.stop()

bets["date_placed"] = pd.to_datetime(bets["date_placed"])
settled = bets[bets["outcome"].isin(["win", "loss", "push"])].copy()
settled["profit"] = settled.apply(
    lambda r: calculate_profit(r["stake"], r["odds_at_placement"], r["outcome"]), axis=1
)
bets["profit"] = bets["outcome"].map(lambda o: None)
bets.loc[settled.index, "profit"] = settled["profit"]

record = (
    f"{(settled['outcome'] == 'win').sum()}-"
    f"{(settled['outcome'] == 'loss').sum()}-"
    f"{(settled['outcome'] == 'push').sum()}"
)
total_staked = settled["stake"].sum()
net_pl = settled["profit"].sum()
roi = (net_pl / total_staked) if total_staked else None

has_clv = bets.dropna(subset=["closing_odds", "odds_at_placement"])
avg_clv = (
    has_clv.apply(lambda r: calculate_clv(r["odds_at_placement"], r["closing_odds"]), axis=1).mean()
    if not has_clv.empty
    else None
)

pl_class = "cp-positive" if net_pl >= 0 else "cp-negative"
roi_class = "cp-positive" if (roi or 0) >= 0 else "cp-negative"
clv_class = "cp-positive" if (avg_clv or 0) >= 0 else "cp-negative"
open_count = bets["outcome"].isna().sum()

st.markdown(
    f"""
    <div class="cp-card cp-scoreboard">
      <div class="cp-stat"><div class="cp-stat-label">Record (W-L-P)</div><div class="cp-stat-value">{record}</div></div>
      <div class="cp-stat"><div class="cp-stat-label">Staked</div><div class="cp-stat-value">${total_staked:,.0f}</div></div>
      <div class="cp-stat"><div class="cp-stat-label">Net P&amp;L</div><div class="cp-stat-value {pl_class}">{net_pl:+,.0f}</div></div>
      <div class="cp-stat"><div class="cp-stat-label">ROI</div><div class="cp-stat-value {roi_class}">{f'{roi:+.1%}' if roi is not None else '—'}</div></div>
      <div class="cp-stat"><div class="cp-stat-label">Avg CLV</div><div class="cp-stat-value {clv_class}">{f'{avg_clv:+.1%}' if avg_clv is not None else '—'}</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)
if open_count:
    st.markdown(f'<div class="cp-empty">{open_count} bet(s) still open, excluded from P&amp;L above.</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="cp-section"><span class="cp-dot" style="background:{}"></span>Cumulative P&amp;L</div>'.format(
        GOOD if net_pl >= 0 else CRITICAL
    ),
    unsafe_allow_html=True,
)
if len(settled) < 2:
    st.markdown('<div class="cp-empty">Need at least two settled bets to chart a trend.</div>', unsafe_allow_html=True)
else:
    st.altair_chart(_pnl_chart(settled), use_container_width=True)

st.markdown('<div class="cp-section"><span class="cp-dot" style="background:{}"></span>Ledger</div>'.format(SLATE), unsafe_allow_html=True)
for _, row in bets.sort_values("date_placed", ascending=False).iterrows():
    st.markdown(_ticket_html(row), unsafe_allow_html=True)
