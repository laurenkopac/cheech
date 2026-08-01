"""
Summarizes the day's news items + top model edges into a newsletter draft.

Every claim in the output must cite its source URL — the prompt enforces
this explicitly.
"""
import os

import anthropic

SUMMARY_PROMPT = """You are drafting a daily NFL newsletter for a single reader.

You will be given a list of news items (title, source, url) and a list of
the model's top predicted edges for upcoming games.

Write a concise, well-organized summary:
- Group related news items together (by team or storyline).
- Every factual claim must include the source URL it came from, inline.
- After the news summary, list the top model edges with their predicted
  probability and market.
- Do not invent facts or sources. If you're unsure, omit the claim.

News items:
{news_items}

Model edges:
{model_edges}
"""


def draft_newsletter(news_items: list[dict], model_edges: list[dict]) -> str:
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
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": SUMMARY_PROMPT.format(news_items=news_block, model_edges=edges_block),
        }],
    )
    return "".join(block.text for block in response.content if block.type == "text")
