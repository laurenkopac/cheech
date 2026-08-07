"""
Renders the structured dict from draft_newsletter() (see summarize.py) into
HTML and plain-text newsletter bodies, styled after the card-based layout in
src/newsletter_example/ (monospace headers, colored category pill badges on
white bordered cards over a light gray page).

Kept separate from send.py so the rendering logic is testable without SMTP.
"""
import re
from datetime import datetime

import markdown
from jinja2 import Environment, select_autoescape
from markupsafe import Markup

CATEGORY_COLORS = {
    "Injury": ("#fee2e2", "#b91c1c"),
    "Roster": ("#ede9fe", "#6d28d9"),
    "Trade": ("#dbeafe", "#1d4ed8"),
    "Line Movement": ("#fef3c7", "#92400e"),
    "General": ("#f4f4f5", "#52525b"),
}
DEFAULT_CATEGORY_COLOR = CATEGORY_COLORS["General"]

# Per-market pill for the Modeling section, keyed by a normalized (lowercase)
# market name. "winner", "anytime_td", and "first_td" are all produced by
# predict_dag; "td_scorer" is here pre-emptively for any other TD-shaped
# market that isn't modeled yet (see CLAUDE.md open decisions).
MARKET_BADGES = {
    "winner": ("Picks", "#cffafe", "#0e7490"),
    "anytime_td": ("TD", "#dcfce7", "#15803d"),
    "first_td": ("TD", "#dcfce7", "#15803d"),
    "td_scorer": ("TD", "#dcfce7", "#15803d"),
}
DEFAULT_MARKET_BADGE_COLOR = ("#f4f4f5", "#52525b")


def _market_badge(market: str) -> tuple:
    key = (market or "").strip().lower().replace(" ", "_")
    if key in MARKET_BADGES:
        return MARKET_BADGES[key]
    if "td" in key:
        return ("TD", "#dcfce7", "#15803d")
    label = market.strip().title() if market else "Model"
    return (label, *DEFAULT_MARKET_BADGE_COLOR)

_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

_env = Environment(autoescape=select_autoescape(["html"]))

# summary_html is pre-rendered markdown wrapped in Markup() by _prepare(),
# so it's explicitly marked safe rather than relying on a blanket |safe
# filter — everything else here is auto-escaped.
_HTML_TEMPLATE = _env.from_string("""\
<html>
  <head>
    <style>
      body { margin: 0; padding: 0; background-color: #f7f7f6; }
      .container {
        max-width: 640px; margin: 0 auto; padding: 32px 24px;
        font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
        color: #18181b;
      }
      .title { font-size: 28px; font-weight: 700; margin: 0 0 6px 0; }
      .subtitle { font-size: 16px; font-weight: 700; color: #71717a; margin: 0 0 16px 0; }
      .intro {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-style: italic; color: #52525b; font-size: 14px; line-height: 1.5;
        margin: 0 0 28px 0;
      }
      .section { font-size: 20px; font-weight: 700; margin: 32px 0 12px 0; }
      .subsection { font-size: 16px; font-weight: 700; margin: 20px 0 10px 0; }
      .card {
        background: #ffffff; border: 1px solid #e4e4e7; border-radius: 12px;
        padding: 20px 22px; margin-bottom: 14px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      }
      .badge {
        display: inline-block; padding: 4px 12px; border-radius: 999px;
        font-size: 12px; font-weight: 600; margin-bottom: 10px;
      }
      .headline { margin: 0 0 8px 0; font-weight: 700; font-size: 16px; }
      .headline a { color: #18181b; text-decoration: underline; }
      .body-text { font-size: 14px; line-height: 1.6; color: #3f3f46; }
      .body-text p { margin: 0; }
      .body-text a { color: #1d4ed8; }
      .empty { font-style: italic; color: #a1a1aa; font-size: 14px; }
    </style>
  </head>
  <body>
    <div class="container">
      <div class="title">Cheech NFL Daily</div>
      <div class="subtitle">{{ date_label }}</div>
      {% if intro %}<div class="intro">{{ intro }}</div>{% endif %}

      <div class="section">News</div>
      {% if news_sections %}
        {% for section in news_sections %}
          <div class="subsection">{{ section.heading }}</div>
          {% for item in section['items'] %}
            {% set colors = category_colors.get(item.category, default_color) %}
            <div class="card">
              <span class="badge" style="background:{{ colors[0] }}; color:{{ colors[1] }};">{{ item.category }}</span>
              <div class="headline"><a href="{{ item.url }}">{{ item.headline }}</a></div>
              <div class="body-text">{{ item.summary_html }}</div>
            </div>
          {% endfor %}
        {% endfor %}
      {% else %}
        <p class="empty">No news items today.</p>
      {% endif %}

      <div class="section">Modeling</div>
      {% if model_edges %}
        {% for edge in model_edges %}
          <div class="card">
            <span class="badge" style="background:{{ edge.badge_bg }}; color:{{ edge.badge_fg }};">{{ edge.badge_label }}</span>
            <div class="headline">{{ edge.subject }}</div>
            <div class="body-text">predicted {{ edge.predicted_probability_pct }}{% if edge.edge_pct %}, edge {{ edge.edge_pct }} vs market{% endif %}</div>
          </div>
        {% endfor %}
      {% else %}
        <p class="empty">No model edges yet.</p>
      {% endif %}
    </div>
  </body>
</html>
""")


def _markdown_to_inline_html(text: str) -> Markup:
    html = markdown.markdown(text, extensions=["nl2br"]).strip()
    if html.startswith("<p>") and html.endswith("</p>"):
        html = html[len("<p>"):-len("</p>")]
    return Markup(html)


def _format_pct(value):
    return f"{value:.1%}" if value is not None else None


def _prepare(data: dict) -> dict:
    news_sections = []
    for section in data.get("news_sections", []):
        items = [
            {**item, "summary_html": _markdown_to_inline_html(item.get("summary", ""))}
            for item in section.get("items", [])
        ]
        news_sections.append({"heading": section.get("heading", ""), "items": items})

    model_edges = []
    for edge in data.get("model_edges", []):
        label, bg, fg = _market_badge(edge.get("market", ""))
        model_edges.append({
            **edge,
            "predicted_probability_pct": _format_pct(edge.get("predicted_probability")),
            "edge_pct": _format_pct(edge.get("edge")),
            "badge_label": label,
            "badge_bg": bg,
            "badge_fg": fg,
        })

    return {
        "intro": data.get("intro", ""),
        "news_sections": news_sections,
        "model_edges": model_edges,
    }


def render_html(data: dict, date_label: str = None) -> str:
    date_label = date_label or datetime.now().strftime("%b %-d, %Y")
    context = _prepare(data)
    return _HTML_TEMPLATE.render(
        date_label=date_label,
        category_colors=CATEGORY_COLORS,
        default_color=DEFAULT_CATEGORY_COLOR,
        **context,
    )


def render_text(data: dict, date_label: str = None) -> str:
    date_label = date_label or datetime.now().strftime("%b %-d, %Y")
    lines = [f"CHEECH NFL DAILY — {date_label}", ""]

    intro = data.get("intro")
    if intro:
        lines += [intro, ""]

    lines += ["NEWS", "===="]
    news_sections = data.get("news_sections", [])
    if not news_sections:
        lines += ["", "No news items today."]
    for section in news_sections:
        lines += ["", section.get("heading", ""), "-" * len(section.get("heading", ""))]
        for item in section.get("items", []):
            summary = _MD_LINK_RE.sub(lambda m: f"{m.group(1)} ({m.group(2)})", item.get("summary", ""))
            lines.append(f"[{item.get('category', 'General')}] {item.get('headline', '')}")
            lines.append(summary)
            lines.append(item.get("url", ""))
            lines.append("")

    lines += ["MODELING", "========"]
    model_edges = data.get("model_edges", [])
    if not model_edges:
        lines += ["", "No model edges yet."]
    for edge in model_edges:
        label, _, _ = _market_badge(edge.get("market", ""))
        pct = _format_pct(edge.get("predicted_probability"))
        edge_pct = _format_pct(edge.get("edge"))
        detail = f"predicted {pct}" + (f", edge {edge_pct} vs market" if edge_pct else "")
        lines.append(f"[{label}] {edge.get('subject', '')} — {detail}")

    return "\n".join(lines)
