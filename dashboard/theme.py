"""
Shared design tokens + base CSS for the Cheech Streamlit dashboard.

Both dashboard/pages/*.py import from here rather than each carrying its
own copy -- unlike the newsletter/Discord palette (src/newsletter/render.py,
src/discord/content.py), which duplicates on purpose because those are
independently-evolving delivery channels, these two pages are meant to
read as one product and should never visually drift apart.

Status colors (GOOD/CRITICAL) come from the dataviz skill's fixed status
scale, not this app's own palette -- "good/bad" is a reserved semantic
that should mean the same thing everywhere a reader sees it, not get
reinvented per project.
"""
import streamlit as st

INK = "#0A0E14"
PANEL = "#12161F"
PANEL_RAISED = "#171C27"
BORDER = "rgba(255,255,255,0.07)"
BORDER_STRONG = "rgba(255,255,255,0.14)"
CHALK = "#F4F6F8"
SLATE = "#8A93A6"
MUTED = "#5B6478"

CYAN = "#4CD9E8"
GREEN = "#3DDC97"
AMBER = "#FFB454"

GOOD = "#0ca30c"
CRITICAL = "#d03b3b"

FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Space+Grotesk:wght@500;600;700"
    "&family=Inter:wght@400;500;600"
    "&family=IBM+Plex+Mono:wght@400;500;600&display=swap');"
)

BASE_CSS = f"""
<style>
{FONT_IMPORT}

[data-testid="stDecoration"] {{ display: none; }}
.stApp {{ background: {INK}; font-family: 'Inter', sans-serif; }}
[data-testid="stHeader"] {{ background: {INK}; }}
[data-testid="stHeader"] svg {{ fill: {SLATE}; }}
[data-testid="stToolbar"] {{ background: {INK}; }}
[data-testid="stSidebar"] {{ background: {PANEL}; border-right: 1px solid {BORDER}; color: {SLATE}; font-family: 'Inter', sans-serif; }}
/* Inheritance only -- a blanket "[data-testid=stSidebar] *" rule out-specifies
   Streamlit's own icon-font class (the nav item icons), turning them into
   literal ligature text instead of a glyph. See dashboard/pages/1_Predictions.py's
   git history for the same bug hit once already on .stApp span/div. */
[data-testid="stSidebarNav"] a, [data-testid="stSidebarNav"] span {{ color: {SLATE}; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{ color: {CHALK}; background: {PANEL_RAISED}; }}
.block-container {{ padding-top: 3.25rem; max-width: 1120px; }}

[data-testid="stButton"] button {{
    background: {PANEL_RAISED}; color: {SLATE}; border: 1px solid {BORDER_STRONG}; border-radius: 8px;
    font-family: 'IBM Plex Mono', monospace; letter-spacing: 0.08em; text-transform: uppercase; font-size: 0.72rem;
}}
[data-testid="stButton"] button:hover {{ border-color: {CYAN}; color: {CYAN}; }}

[data-testid="stExpander"] {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 12px; margin-top: 0.4rem; }}
[data-testid="stExpander"] summary {{
    font-family: 'IBM Plex Mono', monospace; color: {SLATE} !important; font-size: 0.72rem;
    letter-spacing: 0.08em; text-transform: uppercase;
}}
[data-testid="stAlert"] {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 12px; }}
[data-testid="stAlert"] p {{ color: {SLATE} !important; font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem; }}

.cp-title {{
    font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 2.1rem;
    color: {CHALK}; margin: 0; letter-spacing: -0.01em;
}}
.cp-subtitle {{
    font-family: 'IBM Plex Mono', monospace; color: {SLATE}; letter-spacing: 0.14em;
    font-size: 0.75rem; text-transform: uppercase; margin: 0.4rem 0 0 0;
}}
.cp-section {{
    font-family: 'IBM Plex Mono', monospace; letter-spacing: 0.18em; text-transform: uppercase;
    font-size: 0.72rem; font-weight: 600; color: {SLATE}; margin: 2.4rem 0 1rem 0; padding-bottom: 0.6rem;
    border-bottom: 1px solid {BORDER}; display: flex; align-items: center; gap: 0.6rem;
}}
.cp-dot {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; }}
.cp-empty {{ font-family: 'IBM Plex Mono', monospace; color: {MUTED}; font-size: 0.85rem; padding: 0.6rem 0 1.2rem 0; }}
.cp-card {{
    background: {PANEL}; border: 1px solid {BORDER}; border-radius: 16px;
    padding: 1.2rem 1.5rem; margin-bottom: 0.7rem;
    box-shadow: 0 1px 2px rgba(0,0,0,0.35);
}}
</style>
"""


def inject_base_css():
    st.markdown(BASE_CSS, unsafe_allow_html=True)
