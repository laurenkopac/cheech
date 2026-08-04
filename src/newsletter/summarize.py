"""
Summarizes the day's news items + top model edges into a structured
newsletter draft (dict, not markdown) so send.py can render it into the
card-based HTML layout without re-parsing prose.

Every claim must cite its source URL — the prompt enforces this explicitly,
either via the card's own `url` field or an inline markdown link in
`summary` when a claim draws on a different item's source.
"""
import json
import os

import anthropic

SUMMARY_PROMPT = """You are drafting a daily NFL newsletter for a single reader, formatted as
structured data for a card-based template — not prose or markdown.

Return ONLY valid JSON matching this exact schema, with no prose before or
after it:

{{
  "intro": "one italicized teaser sentence summarizing today's newsletter",
  "news_sections": [
    {{
      "heading": "team name or storyline this group of items is about",
      "items": [
        {{
          "category": "one of: Injury, Roster, Trade, Line Movement, General",
          "headline": "short headline for the story",
          "url": "this item's source URL, exactly as given below",
          "summary": "1-3 sentence summary. If a claim draws on a
            different item's source than this card's own url, cite it
            inline as a markdown link: [source](url). Never state a claim
            you cannot cite."
        }}
      ]
    }}
  ],
  "model_edges": [
    {{
      "subject": "matchup or player the prediction is about",
      "market": "market name, e.g. winner",
      "predicted_probability": 0.0 to 1.0,
      "edge": 0.0 to 1.0, or null if not available
    }}
  ]
}}

Rules:
- Group related news items together under one heading, by team or storyline.
- Do not invent facts, sources, or URLs. If you're unsure, omit the item.
- Only use the news items and model edges given below — no outside knowledge.
- If there is no news or no model edges, return an empty list for that key.

News items:
{news_items}

Model edges:
{model_edges}
"""


def draft_newsletter(news_items: list[dict], model_edges: list[dict]) -> dict:
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    news_block = "\n".join(
        f"- {item['title']} ({item['source']}) — {item['url']}" for item in news_items
    )
    edges_block = "\n".join(
        f"- {edge['market']}: {edge['subject']} — {edge['predicted_probability']:.1%}"
        for edge in model_edges
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        messages=[{
            "role": "user",
            "content": SUMMARY_PROMPT.format(news_items=news_block, model_edges=edges_block),
        }],
    )
    text = "".join(block.text for block in response.content if block.type == "text").strip()

    # The prompt asks for raw JSON, but models sometimes wrap it in a
    # ```json fence anyway — strip that before parsing rather than fail.
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(text)
